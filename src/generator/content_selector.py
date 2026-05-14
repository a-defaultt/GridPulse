# src/generator/content_selector.py
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def select_newsletter_content(articles: List[Dict], limit: int = 15) -> List[Dict]:
    """
    Select the top N articles for the newsletter.
    Articles are expected to be ranked by relevance_score.
    """
    selected = articles[:limit]
    logger.info(f"Content selection: Picked top {len(selected)} of {len(articles)} articles")
    
    # Mark as featured if it has a very high score or specific criteria
    for i, a in enumerate(selected):
        if i < 3 or a.get('relevance_score', 0) > 10.0:
            a['is_featured'] = 1
        else:
            a['is_featured'] = 0
            
    return selected
