# src/processor/deduplicator.py
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def deduplicate_articles(articles: List[Dict]) -> List[Dict]:
    """
    Deduplicate articles based on URL and Title within the current list.
    """
    seen_urls = set()
    seen_titles = set()
    unique = []
    
    for a in articles:
        url = a.get('url')
        title = a.get('title', '').strip().lower()
        
        if url in seen_urls:
            logger.debug(f"Duplicate URL: {url}")
            continue
        if title in seen_titles and len(title) > 10: # Avoid deduping very short common titles
            logger.debug(f"Duplicate Title: {title}")
            continue
            
        seen_urls.add(url)
        seen_titles.add(title)
        unique.append(a)
        
    logger.info(f"Deduplication: {len(articles)} -> {len(unique)} articles")
    return unique
