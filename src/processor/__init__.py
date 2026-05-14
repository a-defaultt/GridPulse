# src/processor/__init__.py
from .freshness import filter_fresh_articles
from .categorizer import process_categories
from .deduplicator import deduplicate_articles
from .ranker import rank_articles
from .cross_edition_dedup import CrossEditionDeduplicator

def process_all(articles: list[dict], db_path: str) -> list[dict]:
    """
    Full processing pipeline for articles.
    """
    if not articles:
        return []
        
    # 1. Internal Dedup
    articles = deduplicate_articles(articles)
    
    # 2. Freshness
    articles = filter_fresh_articles(articles, days=7)
    
    # 3. Categorization & CVE extraction
    articles = process_categories(articles)
    
    # 4. Cross-Edition Dedup
    ced = CrossEditionDeduplicator(db_path)
    articles = ced.filter_candidates(articles)
    
    # 5. Ranking
    articles = rank_articles(articles)
    
    return articles
