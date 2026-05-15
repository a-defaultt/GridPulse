# src/aggregator/nvd_client.py
import logging
import requests
import time
from typing import List, Dict, Optional
from src.config import NVD_API_KEY
from src.utils.datetime_utils import utc_now, dt_to_str

logger = logging.getLogger(__name__)

def fetch_nvd_cves(days: int = 1) -> List[Dict]:
    """
    Fetch recent CVEs from NVD API.
    """
    base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    
    logger.info(f"Fetching recent CVEs from NVD (last {days} days)")
    
    headers = {}
    if NVD_API_KEY:
        headers['apiKey'] = NVD_API_KEY
    
    try:
        response = requests.get(base_url, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        vulnerabilities = data.get('vulnerabilities', [])
        articles = []
        fetched_date = dt_to_str(utc_now())
        
        for v in vulnerabilities:
            cve = v.get('cve', {})
            cve_id = cve.get('id')
            descriptions = cve.get('descriptions', [])
            summary = descriptions[0].get('value') if descriptions else "No description"
            
            metrics = cve.get('metrics', {})
            cvss_v3 = metrics.get('cvssMetricV31', metrics.get('cvssMetricV30', []))
            cvss_score = cvss_v3[0].get('cvssData', {}).get('baseScore') if cvss_v3 else None
            
            articles.append({
                'title': f"{cve_id}: {summary[:100]}...",
                'url': f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                'source': 'NVD',
                'source_type': 'api',
                'published_date': cve.get('published'),
                'fetched_date': fetched_date,
                'summary': summary,
                'content': '',
                'topics': 'cve,vulnerability',
                'cvss_score': cvss_score,
                'cve_id': cve_id,
            })
            
        return articles

    except Exception as e:
        logger.error(f"Error fetching from NVD: {e}")
        return []

def get_cve_details(cve_id: str) -> Optional[Dict]:
    """Fetch specific CVE details."""
    base_url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    params = {}
    if NVD_API_KEY:
        params['apiKey'] = NVD_API_KEY
        
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        vulns = data.get('vulnerabilities', [])
        return vulns[0].get('cve') if vulns else None
    except Exception as e:
        logger.error(f"Error fetching CVE {cve_id}: {e}")
        return None
