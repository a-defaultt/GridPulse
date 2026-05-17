"""
AbuseIPDB Client — Verified malicious IP blacklist.
Uses the existing ABUSEIPDB_API_KEY already in .env for Wazuh integration.
Endpoint: /api/v2/blacklist
Free tier: 1,000 requests/day — this uses 1 request per run.
"""

import logging
import requests
from src.config import ABUSEIPDB_API_KEY
from src.utils.datetime_utils import dt_to_str, utc_now

logger = logging.getLogger(__name__)

ABUSEIPDB_URL    = "https://api.abuseipdb.com/api/v2/blacklist"
CONFIDENCE_LIMIT = 90      # Only IPs with 90%+ abuse confidence score
MAX_IPS          = 500     # Cap to avoid bloating the CSV


def fetch_recent_iocs() -> list[dict]:
    """
    Fetches the AbuseIPDB blacklist — confirmed malicious IPs
    with a confidence score >= CONFIDENCE_LIMIT.

    Returns [] on any failure — never raises.
    """
    if not ABUSEIPDB_API_KEY:
        logger.warning("[AbuseIPDB] ABUSEIPDB_API_KEY not set. Skipping.")
        return []

    try:
        logger.info(f"[AbuseIPDB] Fetching blacklist (confidence >= {CONFIDENCE_LIMIT})...")
        response = requests.get(
            ABUSEIPDB_URL,
            headers={
                "Key":    ABUSEIPDB_API_KEY,
                "Accept": "application/json",
            },
            params={
                "confidenceMinimum": CONFIDENCE_LIMIT,
                "limit":             MAX_IPS,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        raw_entries = data.get("data", [])
        logger.info(f"[AbuseIPDB] {len(raw_entries)} IPs received.")
        return _normalize(raw_entries)

    except requests.exceptions.Timeout:
        logger.error("[AbuseIPDB] Request timed out. Skipping.")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"[AbuseIPDB] Network error: {e}. Skipping.")
        return []
    except Exception as e:
        logger.error(f"[AbuseIPDB] Unexpected error: {e}. Skipping.")
        return []


def _normalize(entries: list[dict]) -> list[dict]:
    fetched_at = dt_to_str(utc_now())
    normalized = []
    for entry in entries:
        ip = entry.get("ipAddress", "").strip()
        if not ip:
            continue
        normalized.append({
            "ioc_value":      ip,
            "ioc_type":       "ip",
            "source":         "AbuseIPDB",
            "confidence":     entry.get("abuseConfidenceScore"),
            "malware_family": None,
            "threat_type":    entry.get("usageType", "Unknown"),
            "linked_article": None,
            "fetched_at":     fetched_at,
        })
    return normalized
