# src/generator/__init__.py
from .content_selector import select_newsletter_content
from .summary_generator import generate_summaries_batch
from .daily_generator import generate_daily_newsletter
from .weekly_generator import generate_weekly_newsletter

def generate_newsletter_all(articles: list[dict], edition: str, db_path: str) -> dict:
    """
    Unified entry point for newsletter generation.
    """
    import sqlite3
    
    # 1. Select content
    selected = select_newsletter_content(articles)
    
    # 2. Generate LLM summaries
    selected = generate_summaries_batch(selected)
    
    # 3. Get next edition number
    edition_number = 1
    with sqlite3.connect(db_path) as conn:
        row = conn.execute('SELECT MAX(edition_number) FROM newsletters WHERE edition_type = ?', (edition,)).fetchone()
        if row and row[0]:
            edition_number = row[0] + 1
            
    # 4. Generate content based on edition
    if edition == 'daily':
        return generate_daily_newsletter(selected, edition_number)
    elif edition == 'weekly':
        return generate_weekly_newsletter(selected, edition_number)
    else:
        # Placeholder for monthly
        return {
            'subject': f"GridPulse {edition.capitalize()} Newsletter",
            'content_html': "<h1>Coming Soon</h1>",
            'content_text': "Coming soon.",
            'article_count': len(selected)
        }
