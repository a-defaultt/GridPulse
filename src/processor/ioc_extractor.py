# src/processor/ioc_extractor.py
import re
import logging
from typing import List, Dict, Set

logger = logging.getLogger(__name__)

# Basic Regex Patterns for common IOCs
IOC_PATTERNS = {
    'ip_address': r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
    'domain': r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\b',
    'sha256': r'\b[a-fA-F0-9]{64}\b',
    'sha1': r'\b[a-fA-F0-9]{40}\b',
    'md5': r'\b[a-fA-F0-9]{32}\b',
}

def extract_iocs(text: str) -> List[Dict[str, str]]:
    """
    Extract Indicators of Compromise (IOCs) from text using regex.
    Returns a list of unique IOC dictionaries.
    """
    if not text:
        return []

    found_iocs = []
    seen = set()

    for ioc_type, pattern in IOC_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            val = match.lower() if ioc_type in ['domain'] else match
            if (ioc_type, val) not in seen:
                # Basic validation for domains to avoid common false positives (like source names or common file extensions)
                if ioc_type == 'domain':
                    if val.endswith(('.exe', '.dll', '.bin', '.com', '.org', '.net')):
                         # Further filter: ignore common clean domains if needed, but for now we keep them
                         pass
                    if val.count('.') < 1:
                        continue
                
                found_iocs.append({'type': ioc_type, 'value': val})
                seen.add((ioc_type, val))

    return found_iocs

def process_article_iocs(articles: List[Dict]) -> List[Dict]:
    """
    Extract IOCs from a list of articles and associate them with each article.
    """
    for a in articles:
        text_to_scan = f"{a['title']} {a['summary']} {a.get('content', '')}"
        a['iocs'] = extract_iocs(text_to_scan)
    return articles

def get_all_unique_iocs(articles: List[Dict]) -> List[Dict]:
    """
    Aggregate all unique IOCs from a list of articles.
    """
    all_iocs = []
    seen = set()
    for a in articles:
        for ioc in a.get('iocs', []):
            key = (ioc['type'], ioc['value'])
            if key not in seen:
                # Add source info
                ioc_entry = ioc.copy()
                ioc_entry['source_article'] = a['title']
                ioc_entry['source_url'] = a['url']
                all_iocs.append(ioc_entry)
                seen.add(key)
    return all_iocs
