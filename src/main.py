# src/main.py — Pipeline orchestrator. Never run directly.
import os
import logging
from src.config.source_manager import SourceManager
from src.config import DATABASE_PATH, SOURCES_YAML

logger = logging.getLogger(__name__)

"""
Pipeline Error Policy:
1. Source fetch failures  → CONTINUE (log, mark failed, skip source)
2. Per-article processing → CONTINUE (log, skip article)
3. Newsletter generation  → ABORT (do not send partial output)
4. Email delivery failure → RETRY 3x with 60s backoff; on total failure save draft
5. Database failures      → ABORT immediately
"""

from src.aggregator import fetch_all_sources
from src.processor import process_all
from src.generator import generate_newsletter_all
from src.delivery.email_sender import send_individual_emails
from src.processor.ioc_extractor import process_article_iocs, get_all_unique_iocs
from src.utils.csv_utils import generate_ioc_csv
from src.utils.datetime_utils import dt_to_str, utc_now
import time

from src.database.db_handler import init_db

def run_pipeline(edition: str, dry_run: bool = False):
    db_path = DATABASE_PATH
    yaml_path = SOURCES_YAML
    
    # Ensure DB is initialized
    init_db()

    sm = SourceManager(yaml_path, db_path)  # Singleton for this run
    sources = sm.get_enabled_sources()
    logger.info(f"Starting {edition} pipeline with {len(sources)} sources")

    # --- Stage 1: Fetch ---
    articles = fetch_all_sources(sources)

    if not articles:
        logger.error("No articles fetched from any source. Aborting.")
        return

    # --- Stage 2: Process ---
    processed = process_all(articles, db_path)
    if not processed:
        logger.error("No articles survived processing. Aborting.")
        return

    # --- Stage 3: Generate --- (raises on failure → aborts pipeline)
    newsletter = generate_newsletter_all(processed, edition, db_path)

    # --- Stage 3.5: Extract IOCs for CSV attachment ---
    # We include all unique IOCs from processed articles.
    processed_with_iocs = process_article_iocs(processed)
    iocs = get_all_unique_iocs(processed_with_iocs)
        
    ioc_csv_content = generate_ioc_csv(iocs)
    ioc_filename = f"gridpulse_iocs_{edition}_{utc_now().strftime('%Y%m%d')}.csv"

    # --- Stage 4: Deliver ---
    if not dry_run:
        # Retry logic for delivery
        max_attempts = 3
        backoff = 60
        for attempt in range(max_attempts):
            try:
                send_individual_emails(newsletter, attachment_content=ioc_csv_content, attachment_filename=ioc_filename)
                # Success! Record in DB
                import sqlite3
                with sqlite3.connect(db_path) as conn:
                    conn.execute('PRAGMA journal_mode=WAL;')
                    conn.execute('''
                        INSERT OR REPLACE INTO newsletters (edition_type, edition_number, subject, article_count, sent_date, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        edition, 
                        newsletter.get('edition_number', 1),
                        newsletter['subject'],
                        newsletter['article_count'],
                        dt_to_str(utc_now()),
                        'sent'
                    ))
                logger.info(f"Pipeline completed. Newsletter '{newsletter['subject']}' sent.")
                break
            except Exception as e:
                logger.error(f"Delivery attempt {attempt+1} failed: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(backoff)
                else:
                    logger.error("All delivery attempts failed.")
    else:
        logger.info("Dry run — newsletter not sent. Content logged at DEBUG level.")
        logger.debug(newsletter.get('content_text', ''))
        if ioc_csv_content:
            logger.debug(f"Generated IOC CSV ({len(iocs)} items): {ioc_filename}")
