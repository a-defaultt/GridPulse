"""
OpenPhish Client — Community feed of verified active phishing URLs.
No authentication required.
Feed refreshes every 12 hours.
Cache: Results are written to data/openphish_cache.json and reused for
       the rest of the calendar day to avoid redundant network fetches.
"""

import json
import logging
import os

import requests
from urllib.parse import urlparse
from src.utils.datetime_utils import dt_to_str, utc_now

logger = logging.getLogger(__name__)

OPENPHISH_URL    = "https://openphish.com/feed.txt"
REQUEST_TIMEOUT  = 30
CACHE_FILE       = "data/openphish_cache.json"


def fetch_recent_iocs() -> list[dict]:
    """
    Fetches verified phishing URLs from OpenPhish community feed.
    Each URL is also decomposed into its domain for broader
    threat-hunting coverage in the CSV.

    Results are cached to disk for the calendar day so that running
    multiple pipeline editions on the same day only hits the network once.

    Returns [] on any failure — never raises.
    """
    today = utc_now().strftime("%Y-%m-%d")

    # Return cached result if fetched today
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cached = json.load(f)
            if cached.get("date") == today:
                logger.info(f"[OpenPhish] Using cached result ({len(cached['iocs'])} IOCs).")
                return cached["iocs"]
        except Exception as e:
            logger.warning(f"[OpenPhish] Cache read failed ({e}). Re-fetching.")

    try:
        logger.info("[OpenPhish] Fetching phishing URL feed...")
        response = requests.get(OPENPHISH_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        lines = [
            line.strip() for line in response.text.splitlines()
            if line.strip() and line.startswith("http")
        ]
        logger.info(f"[OpenPhish] {len(lines)} phishing URLs received.")
        normalized = _normalize(lines)

        # Save to cache before returning
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump({"date": today, "iocs": normalized}, f)

        return normalized

    except requests.exceptions.Timeout:
        logger.error("[OpenPhish] Request timed out. Skipping.")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"[OpenPhish] Network error: {e}. Skipping.")
        return []
    except Exception as e:
        logger.error(f"[OpenPhish] Unexpected error: {e}. Skipping.")
        return []


def _normalize(urls: list[str]) -> list[dict]:
    fetched_at = dt_to_str(utc_now())
    iocs = []

    for url in urls:
        # Add the full URL as an IOC
        iocs.append({
            "ioc_value":      url,
            "ioc_type":       "url",
            "source":         "OpenPhish",
            "confidence":     None,
            "malware_family": None,
            "threat_type":    "Phishing",
            "linked_article": None,
            "fetched_at":     fetched_at,
        })

        # Also extract the domain for DNS/firewall blocking use cases
        try:
            domain = urlparse(url).netloc.lower()
            if domain:
                iocs.append({
                    "ioc_value":      domain,
                    "ioc_type":       "domain",
                    "source":         "OpenPhish",
                    "confidence":     None,
                    "malware_family": None,
                    "threat_type":    "Phishing",
                    "linked_article": None,
                    "fetched_at":     fetched_at,
                })
        except Exception:
            pass   # malformed URL — skip domain extraction silently

    return iocs
