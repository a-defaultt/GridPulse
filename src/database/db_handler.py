# src/database/db_handler.py
import sqlite3
import logging
from pathlib import Path
from src.config import DATABASE_PATH, BASE_DIR

logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA foreign_keys=ON;')
    return conn

def init_db():
    """
    Initialize the database using the schema.sql file.
    """
    schema_path = BASE_DIR / "database" / "schema.sql"
    if not schema_path.exists():
        logger.error(f"Schema file not found: {schema_path}")
        return

    logger.info(f"Initializing database at {DATABASE_PATH}")
    try:
        with get_db_connection() as conn:
            with open(schema_path, 'r') as f:
                conn.executescript(f.read())
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def upsert_articles(articles: list[dict]) -> list[dict]:
    """Persist article metadata and attach database ids to article dicts."""
    if not articles:
        return articles

    with get_db_connection() as conn:
        for article in articles:
            url = article.get('url')
            if not url:
                continue

            conn.execute("""
                INSERT INTO articles
                (title, url, source, source_type, published_date, fetched_date,
                 summary, content, topics, cvss_score, cve_id, relevance_score, is_processed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(url) DO UPDATE SET
                    title = excluded.title,
                    source = excluded.source,
                    source_type = excluded.source_type,
                    published_date = COALESCE(excluded.published_date, articles.published_date),
                    fetched_date = excluded.fetched_date,
                    summary = excluded.summary,
                    content = excluded.content,
                    topics = excluded.topics,
                    cvss_score = excluded.cvss_score,
                    cve_id = COALESCE(excluded.cve_id, articles.cve_id),
                    relevance_score = excluded.relevance_score,
                    is_processed = 1
            """, (
                article.get('title') or 'No Title',
                url,
                article.get('source') or 'Unknown',
                article.get('source_type') or 'unknown',
                article.get('published_date'),
                article.get('fetched_date'),
                article.get('summary'),
                article.get('full_content') or article.get('content'),
                article.get('topics'),
                article.get('cvss_score'),
                article.get('cve_id'),
                article.get('relevance_score'),
            ))
            row = conn.execute('SELECT id FROM articles WHERE url = ?', (url,)).fetchone()
            if row:
                article['id'] = row[0]

    logger.info(f"Persisted {len(articles)} articles")
    return articles


def record_newsletter(newsletter: dict, edition: str, articles: list[dict], status: str = 'sent') -> int:
    """Persist a newsletter send and link selected articles for reuse filtering."""
    from src.utils.datetime_utils import dt_to_str, utc_now

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO newsletters
            (edition_type, edition_number, subject, content_html, content_text, article_count, sent_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(edition_type, edition_number) DO UPDATE SET
                subject = excluded.subject,
                content_html = excluded.content_html,
                content_text = excluded.content_text,
                article_count = excluded.article_count,
                sent_date = excluded.sent_date,
                status = excluded.status
        """, (
            edition,
            newsletter.get('edition_number', 1),
            newsletter['subject'],
            newsletter.get('content_html'),
            newsletter.get('content_text'),
            newsletter.get('article_count', len(articles)),
            dt_to_str(utc_now()),
            status,
        ))

        row = conn.execute("""
            SELECT id FROM newsletters
            WHERE edition_type = ? AND edition_number = ?
        """, (edition, newsletter.get('edition_number', 1))).fetchone()
        newsletter_id = row[0]

        for position, article in enumerate(articles, start=1):
            article_id = article.get('id')
            if not article_id and article.get('url'):
                row = conn.execute('SELECT id FROM articles WHERE url = ?', (article['url'],)).fetchone()
                article_id = row[0] if row else None
            if not article_id:
                continue

            conn.execute("""
                INSERT OR IGNORE INTO newsletter_articles
                (newsletter_id, article_id, edition_type, edition_number, position, is_featured)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                newsletter_id,
                article_id,
                edition,
                newsletter.get('edition_number', 1),
                position,
                article.get('is_featured', 0),
            ))

    logger.info(f"Recorded newsletter {edition} #{newsletter.get('edition_number', 1)} with {len(articles)} article links")
    return newsletter_id


def get_ai_cache(item_hash: str, model: str, result_type: str) -> bytes | None:
    """Retrieve cached AI result if it exists."""
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT output_data FROM ai_cache
            WHERE hash = ? AND model = ? AND result_type = ?
        """, (item_hash, model, result_type)).fetchone()
        return row[0] if row else None


def set_ai_cache(item_hash: str, provider: str, model: str, result_type: str, input_text: str, output_data: bytes):
    """Store AI result in cache."""
    from src.utils.datetime_utils import dt_to_str, utc_now
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO ai_cache (hash, provider, model, result_type, input_text, output_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(hash, result_type) DO UPDATE SET
                output_data = excluded.output_data,
                created_at = excluded.created_at
        """, (item_hash, provider, model, result_type, input_text, output_data, dt_to_str(utc_now())))


def get_last_sent_date(edition: str) -> str | None:
    """Retrieve the sent_date of the last sent newsletter for the given edition."""
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT sent_date FROM newsletters
            WHERE edition_type = ? AND status = 'sent'
            ORDER BY sent_date DESC LIMIT 1
        """, (edition,)).fetchone()
        return row[0] if row else None

