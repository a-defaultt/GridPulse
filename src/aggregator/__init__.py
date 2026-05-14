# src/aggregator/__init__.py
from .rss_fetcher import fetch_rss_feed
from .vendor_advisories import fetch_adobe_advisories
from .nvd_client import fetch_nvd_cves
from .cisa_kev import fetch_cisa_kev

def fetch_all_sources(sources: list) -> list:
    """
    Unified entry point for fetching from multiple sources.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    all_articles = []
    for source in sources:
        try:
            name = source['name']
            url = source['url']
            config_type = source['config_type']
            
            if config_type == 'rss':
                all_articles.extend(fetch_rss_feed(source))
            elif config_type == 'vendor':
                if 'adobe' in name.lower():
                    # Check if it's the new RSS format or old scraping
                    if 'rss' in url:
                        all_articles.extend(fetch_rss_feed(source))
                    else:
                        all_articles.extend(fetch_adobe_advisories(url))
                else:
                    logger.warning(f"No specific scraper for vendor source: {name}")
            elif config_type == 'api':
                if 'nvd' in name.lower():
                    all_articles.extend(fetch_nvd_cves())
                elif 'cisa' in name.lower():
                    all_articles.extend(fetch_cisa_kev())
                elif 'otx' in name.lower():
                    logger.warning(f"AlienVault OTX fetcher not yet implemented. Skipping {name}")
            else:
                logger.warning(f"Unknown config_type for source {name}: {config_type}")
        except Exception as e:
            logger.error(f"Failed to fetch from {source['name']}: {e}")
            # Continue to next source
            
    return all_articles
