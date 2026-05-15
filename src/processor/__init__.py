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

logger = logging.getLogger(__name__)

def process_all(articles: list[dict], db_path: str) -> list[dict]:
    """
    Full processing pipeline for articles.

    V5.2 Enhancement: When AI_ENHANCEMENTS is enabled, each traditional
    processing step is followed by its AI-powered counterpart.  The AI
    steps *enrich* rather than replace — if an AI call fails, the
    traditional result is preserved.
    """
    if not articles:
        return []

    if AI_ENHANCEMENTS:
        logger.info("AI enhancements ENABLED — semantic dedup, AI categorization, neural reranking active")
    else:
        logger.info("AI enhancements DISABLED — using traditional processing only")

    # 1. Internal Dedup (exact URL/title match — fast, always runs first)
    articles = deduplicate_articles(articles)

    # 1b. Semantic Dedup (AI — catches near-duplicates exact match misses)
    if AI_ENHANCEMENTS:
        articles = semantic_deduplicate(articles)

    # 2. Freshness
    articles = filter_fresh_articles(articles, days=7)

    # 3. Categorization & CVE extraction (keyword baseline — always runs)
    articles = process_categories(articles)

    # 3b. AI Categorization (enriches keyword categories with LLM context)
    if AI_ENHANCEMENTS:
        articles = ai_categorize_batch(articles)

    # 4. Cross-Edition Dedup
    ced = CrossEditionDeduplicator(db_path)
    articles = ced.filter_candidates(articles)

    # 5. Ranking (heuristic baseline — always runs)
    articles = rank_articles(articles)

    # 5b. Neural Reranking (blends neural scores with heuristic scores)
    if AI_ENHANCEMENTS:
        articles = neural_rerank(articles)

    return articles
