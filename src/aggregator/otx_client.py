# src/aggregator/otx_client.py
"""
AlienVault OTX Client — Open Threat Exchange API v1
Fetches verified IOCs from subscribed pulses updated in the last N days.
Acts as a second parallel IOC intelligence stream alongside ThreatFox.

API Docs: https://otx.alienvault.com/api
Requires: OTX_API_KEY in .env (key already exists as placeholder per V5.4 spec)
Free tier: No hard credit limit — rate limited per endpoint.
"""

import logging
import time
from datetime import timedelta
import requests
from src.config import OTX_API_KEY
from src.utils.datetime_utils import dt_to_str, utc_now

logger = logging.getLogger(__name__)

OTX_BASE_URL      = "https://otx.alienvault.com/api/v1"
DEFAULT_LOOKBACK_DAYS = 1
REQUEST_TIMEOUT   = 60      # Increased from 30 to 60 for slow OTX responses
MAX_PAGES         = 5       # Safety cap — each page = 20 pulses, 100 pulses max per run

# Maps OTX indicator types to GridPulse canonical IOC types
IOC_TYPE_MAP = {
    "IPv4":            "ip",
    "IPv6":            "ip",
    "domain":          "domain",
    "hostname":        "domain",
    "URL":             "url",
    "FileHash-MD5":    "hash_md5",
    "FileHash-SHA1":   "hash_sha1",
    "FileHash-SHA256": "hash_sha256",
}

# OTX types we don't handle — skip silently rather than storing junk
_UNSUPPORTED_TYPES = {
    "email", "CVE", "MUTEX", "filepath",
    "YARA", "SSLCertFingerprint", "BitcoinAddress",
}


def fetch_recent_iocs(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> list[dict]:
    """
    Fetches IOCs from OTX pulses modified in the last `lookback_days` days.
    Paginates through subscribed pulses and extracts all supported indicator types.

    Returns [] on any failure — never raises, pipeline always continues.
    """
    if not OTX_API_KEY:
        logger.warning("[OTX] OTX_API_KEY not set. Skipping.")
        return []

    headers = {
        "X-OTX-API-KEY": OTX_API_KEY,
        "Content-Type":  "application/json",
    }

    all_iocs   = []
    page       = 1
    fetched_at = dt_to_str(utc_now())

    logger.info(f"[OTX] Fetching pulses modified in last {lookback_days} day(s)...")

    circuit_breaker_tripped = False

    while page <= MAX_PAGES:
        if circuit_breaker_tripped:
            break

        max_retries = 2  # Reduced to fail faster
        backoff = 3
        success = False

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"{OTX_BASE_URL}/pulses/subscribed",
                    headers=headers,
                    params={
                        "modified_since": _days_ago_iso(lookback_days),
                        "page":           page,
                        "limit":          20,
                    },
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                data = response.json()
                success = True
                break # Success, break out of retry loop

            except requests.exceptions.Timeout:
                logger.error(f"[OTX] Timeout on page {page} (Attempt {attempt+1}/{max_retries}).")
                if attempt < max_retries - 1:
                    time.sleep(backoff * (attempt + 1))
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else "unknown"
                logger.error(f"[OTX] HTTP {status} on page {page} (Attempt {attempt+1}/{max_retries}).")
                if attempt < max_retries - 1:
                    time.sleep(backoff * (attempt + 1))
            except Exception as e:
                logger.error(f"[OTX] Unexpected error on page {page}: {e}. Stopping.")
                break # Don't retry unknown errors

        if not success:
            logger.error(f"[OTX] Failed to fetch page {page} after {max_retries} attempts. Tripping circuit breaker. Skipping remaining pages.")
            circuit_breaker_tripped = True
            break

        pulses = data.get("results", [])
        if not pulses:
            break   # No more pages

        logger.info(f"[OTX] Page {page} — {len(pulses)} pulses received.")

        for pulse in pulses:
            pulse_name     = pulse.get("name", "Unknown Pulse")
            malware_family = _extract_malware_family(pulse)

            for indicator in pulse.get("indicators", []):
                ioc = _normalize_indicator(
                    indicator, pulse_name, malware_family, fetched_at
                )
                if ioc:
                    all_iocs.append(ioc)

        # OTX returns a `next` URL when more pages exist
        if not data.get("next"):
            break
        page += 1

    logger.info(f"[OTX] Total IOCs collected: {len(all_iocs)}")
    return all_iocs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_indicator(
    indicator: dict,
    pulse_name: str,
    malware_family: str,
    fetched_at: str,
) -> dict | None:
    """
    Converts a single OTX indicator entry into the GridPulse IOC schema.
    Returns None for unsupported or malformed indicators.

    GridPulse IOC schema (shared with threatfox_client.py):
    {
        ioc_value, ioc_type, source, confidence,
        malware_family, threat_type, linked_article, fetched_at
    }
    """
    raw_type = indicator.get("type", "")

    if raw_type in _UNSUPPORTED_TYPES:
        return None

    canonical_type = IOC_TYPE_MAP.get(raw_type)
    if not canonical_type:
        logger.debug(f"[OTX] Unknown indicator type '{raw_type}' — skipping.")
        return None

    ioc_value = indicator.get("indicator", "").strip()
    if not ioc_value:
        return None

    return {
        "ioc_value":      ioc_value,
        "ioc_type":       canonical_type,
        "source":         "OTX",
        "confidence":     None,     # OTX doesn't expose a numeric confidence score
        "malware_family": malware_family,
        "threat_type":    pulse_name,   # Pulse name is the closest equivalent
        "linked_article": None,
        "fetched_at":     fetched_at,
    }


def _extract_malware_family(pulse: dict) -> str:
    """
    Attempts to extract a malware family name from pulse tags or name.
    Returns 'Unknown' if nothing useful is found.
    """
    tags = pulse.get("tags", [])
    if tags:
        return tags[0]      # First tag is usually the most specific
    return pulse.get("name", "Unknown")


def _days_ago_iso(days: int) -> str:
    """
    Returns a UTC ISO-8601 string for `days` ago.
    Used for the `modified_since` query parameter.
    """
    dt = utc_now() - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")
