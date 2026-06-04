# src/aggregator/__init__.py
import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .rss_fetcher import fetch_rss_feed
from .vendor_advisories import fetch_adobe_advisories
from .nvd_client import fetch_nvd_cves
from .cisa_kev import fetch_cisa_kev

logger = logging.getLogger(__name__)


def _fetch_one_source(source: dict) -> tuple[list[dict], Optional[str], Optional[str]]:
    name = source['name']
    url = source['url']
    config_type = source['config_type']

    if config_type == 'rss':
        return fetch_rss_feed(source)

    if config_type == 'vendor':
        if 'adobe' in name.lower():
            # Adobe now supports RSS; keep the scraper fallback for older configs.
            if 'rss' in url:
                return fetch_rss_feed(source)
            return fetch_adobe_advisories(url), None, None
        logger.warning(f"No specific scraper for vendor source: {name}")
        return [], None, None

    if config_type == 'api':
        if 'nvd' in name.lower():
            return fetch_nvd_cves(), None, None
        if 'cisa' in name.lower():
            return fetch_cisa_kev(days=7), None, None
        if 'otx' in name.lower():
            logger.warning(f"AlienVault OTX fetcher not yet implemented. Skipping {name}")
            return [], None, None

    logger.warning(f"Unknown config_type for source {name}: {config_type}")
    return [], None, None


def fetch_all_sources(sources: list, source_manager=None, max_workers: int = 8) -> list:
    """
    Unified entry point for fetching from multiple sources.

    Sources are fetched concurrently because RSS/API calls are independent and
    network-bound. Individual source failures are logged and do not abort the run.
    """
    if not sources:
        return []

    all_articles = []
    worker_count = min(max_workers, len(sources))

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_source = {
            executor.submit(_fetch_one_source, source): source
            for source in sources
        }

        for future in as_completed(future_to_source):
            source = future_to_source[future]
            source_name = source.get('name', 'unknown')
            try:
                articles, etag, modified = future.result()
                all_articles.extend(articles)
                if source_manager:
                    source_manager.mark_fetched(
                        source_name, True, 
                        articles_count=len(articles),
                        etag=etag,
                        last_modified=modified
                    )
            except Exception as e:
                logger.error(f"Failed to fetch from {source_name}: {e}")
                if source_manager:
                    source_manager.mark_fetched(source_name, False, error=str(e))

    return all_articles
