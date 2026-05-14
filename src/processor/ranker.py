# src/processor/ranker.py
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def rank_articles(articles: List[Dict]) -> List[Dict]:
    """
    Score and sort articles by relevance.
    Heuristics: CVSS score, KEV presence, source priority, keywords.
    """
    for a in articles:
        score = 0.0
        
        # CVSS Score
        if a.get('cvss_score'):
            score += float(a['cvss_score'])
            
        # KEV
        if 'kev' in a.get('topics', '').split(','):
            score += 5.0
            
        # Source (hardcoded for now, could be dynamic)
        if 'cisa' in a['source'].lower():
            score += 2.0
        if 'nvd' in a['source'].lower():
            score += 1.0
            
        # Keywords in title
        title_lower = a['title'].lower()
        if 'critical' in title_lower:
            score += 1.5
        if 'emergency' in title_lower:
            score += 2.0
        if 'active' in title_lower and 'exploit' in title_lower:
            score += 2.5
            
        a['relevance_score'] = score
        
    # Sort descending
    ranked = sorted(articles, key=lambda x: x.get('relevance_score', 0), reverse=True)
    return ranked
