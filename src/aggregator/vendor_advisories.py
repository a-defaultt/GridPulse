# src/aggregator/vendor_advisories.py
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from src.utils.datetime_utils import utc_now, dt_to_str

logger = logging.getLogger(__name__)

def fetch_adobe_advisories(url: str = "https://helpx.adobe.com/security.html") -> List[Dict]:
    """
    Scrape Adobe Security Bulletins.
    V5 Guard: Raises ValueError if no advisories found.
    """
    logger.info(f"Scraping Adobe Advisories from {url}")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        # Find the security bulletin table/list
        # Based on Flaw 8: The selector security-bulletin-table was fragile.
        # We look for common patterns or specific IDs if known.
        # Adobe often uses a table within a specific div.
        
        advisories = []
        fetched_date = dt_to_str(utc_now())

        # Attempt to find the table - this is a generic heuristic as Adobe's layout changes.
        # In a real scenario, this would be highly specific.
        table = soup.find('table') # Heuristic: first table on the security page
        
        if table:
            rows = table.find_all('tr')[1:] # Skip header
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    title = cols[0].get_text(strip=True)
                    link_tag = cols[0].find('a')
                    link = link_tag['href'] if link_tag else url
                    if not link.startswith('http'):
                        link = "https://helpx.adobe.com" + link
                    
                    published_date = cols[2].get_text(strip=True) # Usually date is in 3rd column
                    
                    advisories.append({
                        'title': title,
                        'url': link,
                        'source': 'Adobe Security Bulletins',
                        'source_type': 'vendor',
                        'published_date': None, # Parsing specific vendor dates is hard, fallback to fetched
                        'fetched_date': fetched_date,
                        'summary': f"Adobe Security Advisory: {title}",
                        'content': '',
                        'topics': 'vendor,adobe,advisory',
                    })

        if len(advisories) == 0:
            # Flaw 8 Fix: Minimum-results guard
            raise ValueError(f"No advisories found on Adobe page: {url}. Scraper may be broken.")

        return advisories

    except requests.RequestException as e:
        logger.error(f"Network error fetching Adobe advisories: {e}")
        raise
    except Exception as e:
        logger.error(f"Error parsing Adobe advisories: {e}")
        raise
