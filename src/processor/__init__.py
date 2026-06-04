# src/processor/__init__.py
from .freshness import filter_fresh_articles
from .categorizer import process_categories
from .deduplicator import deduplicate_articles
from .ranker import rank_articles
from .cross_edition_dedup import CrossEditionDeduplicator

# V5.2 AI-powered processors
from .ai_deduplicator import semantic_deduplicate
from .ai_categorizer import ai_categorize_batch
from .ai_ranker import neural_rerank
from src.config import AI_ENHANCEMENTS

import logging
import time

logger = logging.getLogger(__name__)

def process_all(articles: list[dict], db_path: str) -> list[dict]:
    """
    Full processing pipeline for articles.
    """
    if not articles:
        return []

    if AI_ENHANCEMENTS:
        logger.info("AI enhancements ENABLED — semantic dedup, AI categorization, neural reranking active")
    else:
        logger.info("AI enhancements DISABLED — using traditional processing only")

    # 1. Internal Dedup
    start = time.time()
    articles = deduplicate_articles(articles)
    logger.info(f"Internal dedup took {time.time() - start:.2f}s")

    # 2. Freshness
    start = time.time()
    articles = filter_fresh_articles(articles, days=7)
    logger.info(f"Freshness filtering took {time.time() - start:.2f}s")

    # 2b. Semantic Dedup
    if AI_ENHANCEMENTS:
        start = time.time()
        articles = semantic_deduplicate(articles)
        logger.info(f"Semantic dedup took {time.time() - start:.2f}s")

    # 3. Categorization
    start = time.time()
    articles = process_categories(articles)
    logger.info(f"Traditional categorization took {time.time() - start:.2f}s")

    # 3b. AI Categorization
    if AI_ENHANCEMENTS:
        start = time.time()
        articles = ai_categorize_batch(articles)
        logger.info(f"AI categorization took {time.time() - start:.2f}s")

    # 4. Cross-Edition Dedup
    start = time.time()
    ced = CrossEditionDeduplicator(db_path)
    articles = ced.filter_candidates(articles)
    logger.info(f"Cross-edition dedup took {time.time() - start:.2f}s")

    # 5. Ranking
    start = time.time()
    articles = rank_articles(articles)
    logger.info(f"Traditional ranking took {time.time() - start:.2f}s")

    # 5b. Neural Reranking
    if AI_ENHANCEMENTS:
        start = time.time()
        articles = neural_rerank(articles)
        logger.info(f"Neural reranking took {time.time() - start:.2f}s")

    return articles
