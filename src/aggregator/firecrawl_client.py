# src/aggregator/firecrawl_client.py
"""
Firecrawl Client — Surgical full-content fetcher.
ONLY called on the top-N highest-scoring articles post-ranking,
to stay within the 1,000 credits/month free tier budget.

Budget rule: max 15 articles/day → max 450 credits/month (safe headroom).
API Docs: https://docs.firecrawl.dev/api-reference/endpoint/scrape
Requires: FIRECRAWL_API_KEY in .env
"""

import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.config import FIRECRAWL_API_KEY
from src.utils.datetime_utils import dt_to_str, utc_now

logger = logging.getLogger(__name__)

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/scrape"
MAX_ARTICLES_PER_RUN = 15       # Hard cap — never exceed to protect credit budget
REQUEST_TIMEOUT = 45            # Firecrawl can be slow on heavy pages
MAX_WORKERS = 5                 # Moderate concurrency to avoid overwhelming or triggering rate limits


def _scrape_one(article: dict, headers: dict) -> dict:
    url = article.get("url") or article.get("link")
    if not url:
        return article

    try:
        logger.info(f"[Firecrawl] Crawling: {url}")
        response = requests.post(
            FIRECRAWL_API_URL,
            json={
                "url": url,
                "formats": ["markdown"],      # Markdown only — cheapest format
                "onlyMainContent": True,       # Strip nav/footer noise
                "excludeTags": ["nav", "footer", "aside", "script", "style"],
            },
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()

        if result.get("success") and result.get("data", {}).get("markdown"):
            article["full_content"] = result["data"]["markdown"]
            article["crawled_at"]   = dt_to_str(utc_now())
            logger.info(f"[Firecrawl] Success — {len(article['full_content'])} chars fetched.")
        else:
            logger.warning(f"[Firecrawl] Empty response for {url}. Keeping original summary.")

    except requests.exceptions.Timeout:
        logger.warning(f"[Firecrawl] Timeout on {url}. Keeping original summary.")
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 402:
            # Re-raise to be handled by the orchestrator (stop all)
            raise e
        logger.warning(f"[Firecrawl] HTTP error for {url}: {e}. Keeping original summary.")
    except Exception as e:
        logger.error(f"[Firecrawl] Unexpected error for {url}: {e}. Keeping original summary.")

    return article


def enrich_articles_with_full_content(articles: list[dict]) -> list[dict]:
    """
    Takes the top-N articles, fetches their full markdown content via Firecrawl
    concurrently to reduce latency.
    """
    if not FIRECRAWL_API_KEY:
        logger.warning("[Firecrawl] FIRECRAWL_API_KEY not set. Skipping content enrichment.")
        return articles

    if len(articles) > MAX_ARTICLES_PER_RUN:
        logger.warning(
            f"[Firecrawl] Input has {len(articles)} articles; "
            f"capping at {MAX_ARTICLES_PER_RUN} to protect credit budget."
        )
        articles = articles[:MAX_ARTICLES_PER_RUN]

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type":  "application/json",
    }

    results_map = {a.get('url'): a for a in articles}
    credit_exhausted = False

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {
            executor.submit(_scrape_one, article, headers): article.get('url')
            for article in articles
        }

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                if credit_exhausted:
                    # If credit exhausted, we can't stop the futures already running,
                    # but we can ignore their results if they haven't finished.
                    # Actually, executor.shutdown(wait=False, cancel_futures=True) in Python 3.9+
                    continue

                updated_article = future.result()
                results_map[url] = updated_article
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 402:
                    logger.error("[Firecrawl] 402 Payment Required — credit limit hit. Halting remaining crawls.")
                    credit_exhausted = True
                    # Attempt to cancel pending futures
                    executor.shutdown(wait=False, cancel_futures=True)
                else:
                    logger.warning(f"[Firecrawl] HTTP error: {e}")
            except Exception as e:
                logger.error(f"[Firecrawl] Worker error: {e}")

    # Maintain original order
    return [results_map.get(a.get('url'), a) for a in articles]
