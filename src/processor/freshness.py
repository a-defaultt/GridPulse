# src/processor/freshness.py
import logging
from datetime import timedelta
from src.utils.datetime_utils import utc_now, str_to_dt

logger = logging.getLogger(__name__)

def filter_fresh_articles(articles: list[dict], days: int = 7) -> list[dict]:
    """
    Filter articles published within the last X days.
    If published_date is None, use fetched_date as fallback.
    """
    cutoff = utc_now() - timedelta(days=days)
    fresh = []
    
    for a in articles:
        pub_date = str_to_dt(a.get('published_date'))
        if not pub_date:
            pub_date = str_to_dt(a.get('fetched_date'))
            
        if pub_date and pub_date >= cutoff:
            fresh.append(a)
        else:
            logger.debug(f"Article too old or unparseable date: {a['title']}")
            
    logger.info(f"Freshness filter: {len(articles)} -> {len(fresh)} articles")
    return fresh
