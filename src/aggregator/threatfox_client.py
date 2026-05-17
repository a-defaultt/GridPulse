# src/aggregator/threatfox_client.py
"""
ThreatFox IOC Client — abuse.ch ThreatFox API v1
Fetches verified, community-curated IOCs for the past N hours.
Acts as a parallel intelligence source alongside RSS/NVD/CISA.
API Docs: https://threatfox-api.abuse.ch/api/v1/
No API key required for basic queries.
"""

import logging
import time
import requests
from src.config import THREATFOX_API_KEY
from src.utils.datetime_utils import dt_to_str, utc_now

logger = logging.getLogger(__name__)

THREATFOX_API_URL = "https://threatfox-api.abuse.ch/api/v1/"
DEFAULT_LOOKBACK_DAYS = 1         # For daily runs
CONFIDENCE_THRESHOLD = 75         # Drops low-confidence community submissions

# Maps ThreatFox ioc_type strings to GridPulse canonical types
IOC_TYPE_MAP = {
    "ip:port":     "ip",
    "domain":      "domain",
    "url":         "url",
    "md5_hash":    "hash_md5",
    "sha1_hash":   "hash_sha1",
    "sha256_hash": "hash_sha256",
}


def fetch_recent_iocs(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> list[dict]:
    """
    Queries ThreatFox for IOCs submitted in the last `lookback_days` days.
    Returns a normalized list of IOC dicts ready for the GridPulse CSV pipeline.

    Returns [] on any failure — never raises, always allows pipeline to continue.
    """
    payload = {
        "query": "get_iocs",
        "days":  lookback_days,
    }

    headers = {"Content-Type": "application/json"}
    if THREATFOX_API_KEY:
        headers["API-KEY"] = THREATFOX_API_KEY

    max_retries = 3
    backoff = 2

    for attempt in range(max_retries):
        try:
            logger.info(f"[ThreatFox] Fetching IOCs for last {lookback_days} day(s) (Attempt {attempt+1}/{max_retries})...")
            response = requests.post(
                THREATFOX_API_URL,
                json=payload,
                timeout=45,  # Increased timeout
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("query_status") != "ok":
                logger.warning(f"[ThreatFox] Non-OK status: {data.get('query_status')}")
                return []

            raw_iocs = data.get("data", []) or []
            logger.info(f"[ThreatFox] Raw IOCs received: {len(raw_iocs)}")

            normalized = _normalize_iocs(raw_iocs)
            logger.info(f"[ThreatFox] IOCs after confidence filter (>={CONFIDENCE_THRESHOLD}): {len(normalized)}")
            return normalized

        except requests.exceptions.Timeout:
            logger.error(f"[ThreatFox] Request timed out on attempt {attempt+1}.")
            if attempt < max_retries - 1:
                time.sleep(backoff * (attempt + 1))
            else:
                logger.error("[ThreatFox] Max retries reached. Skipping.")
                return []
        except requests.exceptions.HTTPError as e:
            logger.error(f"[ThreatFox] HTTP Error: {e.response.status_code}. Attempt {attempt+1}")
            if e.response.status_code == 401:
                logger.error("[ThreatFox] 401 Unauthorized. Ensure THREATFOX_API_KEY is set in .env.")
                return [] # 401 won't be fixed by retrying
            
            if attempt < max_retries - 1:
                time.sleep(backoff * (attempt + 1))
            else:
                logger.error("[ThreatFox] Network error limit reached. Skipping.")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"[ThreatFox] Network error: {e}. Attempt {attempt+1}")
            if attempt < max_retries - 1:
                time.sleep(backoff * (attempt + 1))
            else:
                logger.error("[ThreatFox] Max retries reached. Skipping.")
                return []
        except Exception as e:
            logger.error(f"[ThreatFox] Unexpected error: {e}. Skipping.")
            return []


def _normalize_iocs(raw_iocs: list[dict]) -> list[dict]:
    """
    Converts ThreatFox raw entries into the GridPulse IOC schema.
    Filters by confidence threshold and maps type strings to canonical names.

    GridPulse IOC schema:
    {
        "ioc_value":      str,
        "ioc_type":       str,   # canonical type (ip, domain, hash_md5, etc.)
        "source":         str,   # always "ThreatFox"
        "confidence":     int,   # 0–100
        "malware_family": str,
        "threat_type":    str,
        "linked_article": None,  # not linked to a specific article
        "fetched_at":     str,   # UTC ISO-8601
    }
    """
    normalized = []
    fetched_at = dt_to_str(utc_now())

    for entry in raw_iocs:
        confidence = int(entry.get("confidence_level", 0))
        if confidence < CONFIDENCE_THRESHOLD:
            continue

        raw_type = entry.get("ioc_type", "")
        canonical_type = IOC_TYPE_MAP.get(raw_type, raw_type)  # fallback: keep original

        # Strip port from ip:port entries so the CSV value is clean
        ioc_value = entry.get("ioc", "")
        if raw_type == "ip:port" and ":" in ioc_value:
            ioc_value = ioc_value.rsplit(":", 1)[0]

        normalized.append({
            "ioc_value":      ioc_value,
            "ioc_type":       canonical_type,
            "source":         "ThreatFox",
            "confidence":     confidence,
            "malware_family": entry.get("malware", "Unknown"),
            "threat_type":    entry.get("threat_type", "Unknown"),
            "linked_article": None,
            "fetched_at":     fetched_at,
        })

    return normalized
