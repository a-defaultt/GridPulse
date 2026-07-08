"""
Mallory.ai Client — Threat-intel IOC feed + single-IOC enrichment via the
official `malloryapi` SDK (https://pypi.org/project/malloryapi/).

Auth: MALLORY_API_KEY (Bearer token, read from src.config; the SDK also
      auto-reads the env var of the same name, but we pass it explicitly
      to match this repo's "config only via src.config" convention).

Cache: Feed results (fetch_recent_iocs) are written to data/mallory_cache.json
       and reused for the rest of the calendar day, same convention as
       abuseipdb_client.py / openphish_client.py / emerging_threats_client.py.
       Enrichment lookups (enrich_ioc/enrich_iocs) are NOT disk-cached —
       they're per-run, deduped only in-memory.

Field names confirmed live against a real account (2026-07-07):
- Observable: {type, name, description, tags, verdict_counts:{malicious,
  suspicious, benign, unknown}, ...}. No flat 'confidence' field — Mallory
  exposes a verdict breakdown instead, so 'confidence' stays None for feed
  rows and threat_type is derived from tags (or the dominant verdict when
  untagged).
- Opinion (via opinions_by_type_name): {observable_type, observable_name,
  verdict, source, confidence (often None), attributes:{tags}, description,
  url, ...}. Enrichment context comes from the opinion's 'description',
  falling back to its 'verdict'; opinion tags live under attributes.tags
  and are merged with the observable's own tags.
_first()'s defensive multi-key probing is kept as a safety net in case
these shapes drift across accounts/API versions, not because they were
guessed.
"""
import ipaddress
import json
import logging
import os
from typing import Optional

from malloryapi import MalloryApi, NotFoundError, RateLimitError

from src.config import MALLORY_API_KEY, MALLORY_ENRICHMENT_LIMIT
from src.utils.datetime_utils import dt_to_str, utc_now

logger = logging.getLogger(__name__)

CACHE_FILE = "data/mallory_cache.json"
MAX_IOCS = 500  # Cap to avoid bloating the CSV/Sheet, mirrors AbuseIPDB's MAX_IPS

_logged_observable_shape = False
_logged_opinion_shape = False


def fetch_recent_iocs() -> list[dict]:
    """
    Fetches recent observables (IOCs) from Mallory.ai as a new feed source.
    Returns [] on any failure or missing API key — never raises.
    Cached to disk for the calendar day.
    """
    if not MALLORY_API_KEY:
        logger.warning("[Mallory] MALLORY_API_KEY not set. Skipping.")
        return []

    today = utc_now().strftime("%Y-%m-%d")
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cached = json.load(f)
            if cached.get("date") == today:
                logger.info(f"[Mallory] Using cached result ({len(cached['iocs'])} IOCs).")
                return cached["iocs"]
        except Exception as e:
            logger.warning(f"[Mallory] Cache read failed ({e}). Re-fetching.")

    try:
        logger.info("[Mallory] Fetching recent observables...")
        client = MalloryApi(api_key=MALLORY_API_KEY)
        page = client.observables.list(limit=MAX_IOCS)
        raw_entries = list(page)
        logger.info(f"[Mallory] {len(raw_entries)} observables received.")
        normalized = _normalize(raw_entries)

        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump({"date": today, "iocs": normalized}, f)

        return normalized
    except RateLimitError as e:
        logger.error(f"[Mallory] Rate limited: {e}. Skipping.")
        return []
    except Exception as e:
        logger.error(f"[Mallory] Unexpected error fetching feed: {e}. Skipping.")
        return []


def enrich_ioc(ioc_value: str, ioc_type: str) -> Optional[dict]:
    """
    Looks up a single IOC by (type, value) for enrichment context.
    Returns {'confidence': int|None, 'tags': list[str], 'context': str} or
    None if not found / on any error. Never raises.
    """
    global _logged_observable_shape, _logged_opinion_shape

    if not MALLORY_API_KEY:
        return None

    mallory_type = _to_mallory_type(ioc_type, ioc_value)

    try:
        client = MalloryApi(api_key=MALLORY_API_KEY)
        observable = client.observables.get_by_type_name(mallory_type, ioc_value)

        if not _logged_observable_shape:
            logger.debug(f"[Mallory] Sample observable shape: {list(observable.keys())}")
            _logged_observable_shape = True

        result = {
            "confidence": _first(observable, "confidence", "score", "risk_score"),
            "tags": list(_first(observable, "tags", "labels", default=[]) or []),
            "context": _first(observable, "description", "context", "summary", default="") or "",
        }

        try:
            opinions = client.observables.opinions_by_type_name(mallory_type, ioc_value, limit=1)
            top_opinion = next(iter(opinions), None)
            if top_opinion:
                if not _logged_opinion_shape:
                    logger.debug(f"[Mallory] Sample opinion shape: {list(top_opinion.keys())}")
                    _logged_opinion_shape = True
                if result["confidence"] is None:
                    result["confidence"] = _first(top_opinion, "confidence", "score")
                if not result["context"]:
                    verdict = top_opinion.get("verdict")
                    description = _first(top_opinion, "description", "summary")
                    result["context"] = description or verdict or ""
                opinion_tags = _first(top_opinion.get("attributes") or {}, "tags", default=[]) or []
                for t in opinion_tags:
                    if t not in result["tags"]:
                        result["tags"].append(t)
        except Exception as e:
            logger.debug(f"[Mallory] Opinions lookup failed for {ioc_type}:{ioc_value}: {e}")

        return result
    except NotFoundError:
        return None
    except RateLimitError as e:
        logger.warning(f"[Mallory] Rate limited during enrichment: {e}. Stopping further lookups this run.")
        raise
    except Exception as e:
        logger.debug(f"[Mallory] Enrichment lookup failed for {ioc_type}:{ioc_value}: {e}")
        return None


def enrich_iocs(iocs: list[dict], limit: int = None) -> list[dict]:
    """
    Enriches up to `limit` UNIQUE (ioc_type, ioc_value) pairs found in `iocs`
    via Mallory lookups, applying the same enrichment result to every row
    sharing that pair (handles cross-source duplicates from track_and_filter_iocs).
    Returns a NEW list of shallow-copied dicts — never mutates input, never raises.
    Adds/overwrites keys: 'confidence' (only if Mallory has one), 'mallory_tags'
    (comma-joined str), 'mallory_context' (str, truncated to 200 chars).
    """
    limit = MALLORY_ENRICHMENT_LIMIT if limit is None else limit
    if not iocs or not MALLORY_API_KEY:
        return iocs

    cache: dict[tuple, Optional[dict]] = {}
    unique_lookups = 0
    rate_limited = False
    result = []

    for ioc in iocs:
        typ = ioc.get("ioc_type") or ioc.get("type")
        val = ioc.get("ioc_value") or ioc.get("value")
        key = (typ, val)
        out = dict(ioc)

        if key not in cache:
            if rate_limited or unique_lookups >= limit:
                cache[key] = None
            else:
                try:
                    cache[key] = enrich_ioc(val, typ)
                except RateLimitError:
                    cache[key] = None
                    rate_limited = True
                unique_lookups += 1

        enrichment = cache.get(key)
        if enrichment:
            if enrichment.get("confidence") is not None:
                out["confidence"] = enrichment["confidence"]
            if enrichment.get("tags"):
                out["mallory_tags"] = ", ".join(str(t) for t in enrichment["tags"])
            if enrichment.get("context"):
                out["mallory_context"] = enrichment["context"][:200]

        result.append(out)

    total_unique = len({
        (o.get("ioc_type") or o.get("type"), o.get("ioc_value") or o.get("value"))
        for o in iocs
    })
    skipped = max(total_unique - unique_lookups, 0)
    logger.info(
        f"[Mallory] Enriched up to {unique_lookups} unique IOCs "
        f"({len(iocs)} total rows); {skipped} unique IOCs skipped "
        f"beyond MALLORY_ENRICHMENT_LIMIT={limit}"
        + (" (rate limited)" if rate_limited else "") + "."
    )
    return result


def _normalize(entries: list) -> list[dict]:
    """Maps Mallory SDK observable dicts to the common feed shape."""
    global _logged_observable_shape
    fetched_at = dt_to_str(utc_now())
    normalized = []
    for entry in entries:
        if not _logged_observable_shape and entry:
            logger.debug(f"[Mallory] Sample observable shape: {list(entry.keys())}")
            _logged_observable_shape = True

        value = _first(entry, "value", "name", "indicator")
        if not value:
            continue

        tags = entry.get("tags") or []
        threat_type = ", ".join(tags) if tags else _dominant_verdict(entry.get("verdict_counts"))

        normalized.append({
            "ioc_value":      value,
            "ioc_type":       _first(entry, "type", "observable_type", default="unknown"),
            "source":         "Mallory",
            # Mallory exposes a verdict_counts breakdown instead of a flat
            # confidence score — left None here rather than fabricating one.
            "confidence":     _first(entry, "confidence", "score", "risk_score"),
            "malware_family": _first(entry, "malware_family"),
            "threat_type":    threat_type,
            "linked_article": None,
            "fetched_at":     fetched_at,
        })
    return normalized


def _to_mallory_type(ioc_type: str, ioc_value: str) -> str:
    """
    Maps GridPulse's internal ioc_type vocabulary (ip/ip_address, url,
    md5/sha1/sha256, domain) to Mallory's namespaced observable_type
    vocabulary (ip.v4/ip.v6, uri, hash.md5/hash.sha1/hash.sha256, domain),
    confirmed live against a real account (2026-07-07). Lookups with a
    mismatched type return a 400 from Mallory's API, which enrich_ioc's
    caller already treats as a routine per-IOC miss.
    """
    if ioc_type in ("ip", "ip_address"):
        try:
            return "ip.v6" if ipaddress.ip_address(ioc_value).version == 6 else "ip.v4"
        except ValueError:
            return "ip.v4"
    if ioc_type == "url":
        return "uri"
    if ioc_type in ("md5", "sha1", "sha256"):
        return f"hash.{ioc_type}"
    return ioc_type


def _dominant_verdict(verdict_counts: Optional[dict]) -> str:
    """Picks the most severe non-zero verdict bucket as a threat_type fallback."""
    if not verdict_counts:
        return "Unknown"
    for verdict in ("malicious", "suspicious", "benign", "unknown"):
        if verdict_counts.get(verdict, 0) > 0:
            return verdict
    return "Unknown"


def _first(d: dict, *keys: str, default=None):
    """Returns the first present, non-None value among `keys` in dict `d`."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default
