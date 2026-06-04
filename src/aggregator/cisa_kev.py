# src/aggregator/cisa_kev.py
import logging
import requests
from typing import List, Dict
from datetime import timedelta
from src.utils.datetime_utils import utc_now, dt_to_str, str_to_dt

logger = logging.getLogger(__name__)

def fetch_cisa_kev(days: int = 7) -> List[Dict]:
    """
    Fetch Known Exploited Vulnerabilities from CISA.
    Filters by dateAdded to only include recent additions.
    """
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    logger.info(f"Fetching CISA KEV catalog (last {days} days)")
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        vulnerabilities = data.get('vulnerabilities', [])
        articles = []
        now = utc_now()
        cutoff = now - timedelta(days=days)
        fetched_date = dt_to_str(now)
        
        for v in vulnerabilities:
            date_added_str = v.get('dateAdded')
            if date_added_str:
                try:
                    # dateAdded is typically YYYY-MM-DD
                    date_added = str_to_dt(date_added_str)
                    if date_added < cutoff:
                        continue
                except Exception:
                    # If date parsing fails, include it just in case? Or skip?
                    # Let's log and include it.
                    logger.debug(f"Could not parse CISA KEV dateAdded: {date_added_str}")

            cve_id = v.get('cveID')
            vendor = v.get('vendorProject')
            product = v.get('product')
            vulnerability_name = v.get('vulnerabilityName')
            short_description = v.get('shortDescription')
            
            articles.append({
                'title': f"KEV: {cve_id} - {vendor} {product}: {vulnerability_name}",
                'url': f"https://nvd.nist.gov/vuln/detail/{cve_id}", # Redirect to NVD for details
                'source': 'CISA KEV',
                'source_type': 'api',
                'published_date': v.get('dateAdded'),
                'fetched_date': fetched_date,
                'summary': short_description,
                'content': v.get('requiredAction', ''),
                'topics': 'kev,vulnerability,exploited',
                'cve_id': cve_id,
            })
            
        return articles

    except Exception as e:
        logger.error(f"Error fetching CISA KEV: {e}")
        return []
