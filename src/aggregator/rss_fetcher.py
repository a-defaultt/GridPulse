# src/aggregator/rss_fetcher.py
import logging
import feedparser
from typing import List, Dict, Optional
from src.utils.datetime_utils import parse_rss_date, utc_now, dt_to_str

logger = logging.getLogger(__name__)

import re

def fetch_rss_feed(source: Dict) -> tuple[List[Dict], Optional[str], Optional[str]]:
    """
    Fetch and parse an RSS feed.
    Supports incremental fetching via etag and last_modified.
    """
    source_name = source['name']
    url = source['url']
    min_score = source.get('min_score')
    etag = source.get('etag')
    modified = source.get('last_modified')
    
    logger.info(f"Fetching RSS feed for '{source_name}'")
    try:
        # feedparser.parse handles etag and modified headers
        feed = feedparser.parse(url, etag=etag, modified=modified)
        
        if hasattr(feed, 'status') and feed.status == 304:
            logger.info(f"RSS feed '{source_name}' not modified (304).")
            return [], etag, modified

        if feed.bozo:
            logger.warning(f"RSS feed '{source_name}' might be malformed: {feed.bozo_exception}")

        articles = []
        fetched_date = dt_to_str(utc_now())

        for entry in feed.entries:
            # Check min_score for Hacker News (hnrss.org)
            if min_score is not None:
                description = entry.get('summary', '')
                score_match = re.search(r'Points: (\d+)', description)
                if score_match:
                    score = int(score_match.group(1))
                    if score < min_score:
                        continue
            
            published_dt = parse_rss_date(entry.get('published', entry.get('updated', '')))
            published_date_str = dt_to_str(published_dt) if published_dt else None

            article = {
                'title': entry.get('title', 'No Title'),
                'url': entry.get('link', ''),
                'source': source_name,
                'source_type': 'rss',
                'published_date': published_date_str,
                'fetched_date': fetched_date,
                'summary': entry.get('summary', entry.get('description', '')),
                'content': entry.get('content', [{'value': ''}])[0]['value'] if 'content' in entry else '',
                'topics': '', # Categorizer will fill this
                'cve_id': None, # Ranker/Categorizer might extract this
            }
            if article['url']:
                articles.append(article)
            else:
                logger.debug(f"Skipping entry with no URL in '{source_name}'")

        return articles, feed.get('etag'), feed.get('modified')

    except Exception as e:
        logger.error(f"Failed to fetch RSS feed '{source_name}': {e}")
        raise
