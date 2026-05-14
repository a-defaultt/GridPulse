# src/processor/categorizer.py
import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Basic keywords for categorization
TOPIC_KEYWORDS = {
    'ransomware': ['ransomware', 'lockbit', 'clop', 'blackcat'],
    'vulnerability': ['cve', 'vulnerability', 'zero-day', '0-day', 'exploit', 'bug'],
    'malware': ['malware', 'trojan', 'botnet', 'stealer', 'spyware'],
    'data-breach': ['breach', 'leak', 'exposed', 'hack', 'stolen'],
    'state-sponsored': ['apt', 'nation-state', 'state-sponsored', 'china', 'russia', 'north korea', 'iran'],
}

def extract_cve(text: str) -> List[str]:
    """Extract CVE IDs from text."""
    return list(set(re.findall(r'CVE-\d{4}-\d{4,7}', text, re.IGNORECASE)))

def categorize_article(article: Dict) -> Dict:
    """
    Assign topics and extract CVEs for an article.
    """
    content_to_scan = f"{article['title']} {article['summary']} {article.get('content', '')}".lower()
    
    # Extract CVEs
    cves = extract_cve(content_to_scan)
    if cves:
        article['cve_id'] = cves[0].upper() # Take the first one as primary
        
    # Assign topics
    topics = set(article.get('topics', '').split(',')) if article.get('topics') else set()
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in content_to_scan:
                topics.add(topic)
                break
                
    article['topics'] = ','.join(filter(None, topics))
    return article

def process_categories(articles: List[Dict]) -> List[Dict]:
    return [categorize_article(a) for a in articles]
