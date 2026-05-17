"""
Emerging Threats Client — Proofpoint's free compromised IP/domain blocklist.
No authentication required.
Updated daily by Proofpoint's threat research team.
"""

import logging
import requests
from src.utils.datetime_utils import dt_to_str, utc_now

logger = logging.getLogger(__name__)

SOURCES = {
    "ip": "https://rules.emergingthreats.net/blockrules/compromised-ips.txt",
    "domain": "https://rules.emergingthreats.net/blockrules/emerging-botcc.domains",
}
REQUEST_TIMEOUT = 30


def fetch_recent_iocs() -> list[dict]:
    """
    Fetches both compromised IPs and botnet C2 domains
    from Emerging Threats blocklists.

    Returns [] on total failure — never raises.
    """
    all_iocs  = []
    fetched_at = dt_to_str(utc_now())

    for ioc_type, url in SOURCES.items():
        try:
            logger.info(f"[EmergingThreats] Fetching {ioc_type} list from {url}...")
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            lines = response.text.splitlines()
            entries = [
                line.strip() for line in lines
                if line.strip() and not line.startswith("#")
            ]
            
            # Cap at 1000 per type per run to prevent CSV bloat
            entries = entries[:1000]

            logger.info(f"[EmergingThreats] {len(entries)} {ioc_type} entries received (capped at 1000).")

            for value in entries:
                all_iocs.append({
                    "ioc_value":      value,
                    "ioc_type":       ioc_type,
                    "source":         "EmergingThreats",
                    "confidence":     None,
                    "malware_family": None,
                    "threat_type":    "Botnet/C2",
                    "linked_article": None,
                    "fetched_at":     fetched_at,
                })

        except requests.exceptions.Timeout:
            logger.error(f"[EmergingThreats] Timeout fetching {ioc_type}. Skipping.")
        except requests.exceptions.RequestException as e:
            logger.error(f"[EmergingThreats] Error fetching {ioc_type}: {e}. Skipping.")
        except Exception as e:
            logger.error(f"[EmergingThreats] Unexpected error for {ioc_type}: {e}. Skipping.")

    logger.info(f"[EmergingThreats] Total IOCs collected: {len(all_iocs)}")
    return all_iocs
