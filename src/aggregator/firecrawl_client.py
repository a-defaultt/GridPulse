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
from src.config import FIRECRAWL_API_KEY
from src.utils.datetime_utils import dt_to_str, utc_now

logger = logging.getLogger(__name__)

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/scrape"
MAX_ARTICLES_PER_RUN = 15       # Hard cap — never exceed to protect credit budget
REQUEST_TIMEOUT = 45            # Firecrawl can be slow on heavy pages


def enrich_articles_with_full_content(articles: list[dict]) -> list[dict]:
    """
    Takes the top-N articles (already ranked and sliced by the caller),
    fetches their full markdown content via Firecrawl, and injects it
    into each article dict under the key `full_content`.

    Articles that fail to fetch retain their original `summary` field
    so the pipeline continues without interruption (Graceful Fallback rule).

    Args:
        articles: List of article dicts. Must already be sliced to <= MAX_ARTICLES_PER_RUN.

    Returns:
        The same list with `full_content` and `crawled_at` keys injected where successful.
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

    enriched = []
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type":  "application/json",
    }

    for i, article in enumerate(articles):
        url = article.get("url") or article.get("link")
        if not url:
            logger.warning(f"[Firecrawl] Article {i} has no URL — skipping.")
            enriched.append(article)
            continue

        try:
            logger.info(f"[Firecrawl] Crawling ({i+1}/{len(articles)}): {url}")
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
                # 402 = credit limit exhausted — stop immediately, don't waste remaining calls
                logger.error("[Firecrawl] 402 Payment Required — credit limit hit. Halting crawl.")
                enriched.append(article)
                enriched.extend(articles[i+1:])   # Append remaining un-enriched articles
                return enriched
            logger.warning(f"[Firecrawl] HTTP error for {url}: {e}. Keeping original summary.")
        except Exception as e:
            logger.error(f"[Firecrawl] Unexpected error for {url}: {e}. Keeping original summary.")

        enriched.append(article)

    return enriched
