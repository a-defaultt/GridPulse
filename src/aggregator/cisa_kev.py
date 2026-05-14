# src/aggregator/cisa_kev.py
import logging
import requests
from typing import List, Dict
from src.utils.datetime_utils import utc_now, dt_to_str

logger = logging.getLogger(__name__)

def fetch_cisa_kev() -> List[Dict]:
    """
    Fetch Known Exploited Vulnerabilities from CISA.
    """
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    logger.info("Fetching CISA KEV catalog")
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        vulnerabilities = data.get('vulnerabilities', [])
        articles = []
        fetched_date = dt_to_str(utc_now())
        
        for v in vulnerabilities:
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
