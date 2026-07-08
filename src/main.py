# src/main.py — Pipeline orchestrator. Never run directly.
import os
import logging
from src.config.source_manager import SourceManager
from src.config import DATABASE_PATH, SOURCES_YAML
from concurrent.futures import ThreadPoolExecutor

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
from src.aggregator.firecrawl_client import enrich_articles_with_full_content
from src.aggregator.abuseipdb_client import fetch_recent_iocs as fetch_abuseipdb_iocs
from src.aggregator.emerging_threats_client import fetch_recent_iocs as fetch_et_iocs
from src.aggregator.openphish_client import fetch_recent_iocs as fetch_openphish_iocs
from src.aggregator.mallory_client import fetch_recent_iocs as fetch_mallory_iocs, enrich_iocs
from src.delivery.google_sheets_sync import sync_iocs
import time

from src.database.db_handler import init_db, upsert_articles, record_newsletter

def run_pipeline(edition: str, dry_run: bool = False, test_recipient: str | None = None):
    db_path = DATABASE_PATH
    yaml_path = SOURCES_YAML
    
    # Ensure DB is initialized
    init_db()

    sm = SourceManager(yaml_path, db_path)  # Singleton for this run
    sources = sm.get_enabled_sources()
    logger.info(f"Starting {edition} pipeline with {len(sources)} sources")
    if test_recipient:
        logger.info(f"Test delivery mode enabled; sending only to {test_recipient}")

    # --- Stage 1: Fetch ---
    start_time = time.time()
    articles = fetch_all_sources(sources, source_manager=sm)
    logger.info(f"Stage 1 (Fetch) completed in {time.time() - start_time:.2f}s. Fetched {len(articles)} articles.")

    if not articles:
        logger.error("No articles fetched from any source. Aborting.")
        return

    # --- Stage 2: Process ---
    start_time = time.time()
    processed = process_all(articles, db_path)
    if not processed:
        logger.error("No articles survived processing. Aborting.")
        return
    processed = upsert_articles(processed)
    logger.info(f"Stage 2 (Process) completed in {time.time() - start_time:.2f}s. {len(processed)} articles remaining.")

    # --- Stage 2.5: Firecrawl Enrichment (top articles only) ---
    start_time = time.time()
    # Surgical crawl — only the highest-value articles get full content.
    # This runs AFTER ranking so we know which articles matter most.
    top_articles = processed[:15]  # Already sorted by relevance_score from ranker
    top_articles = enrich_articles_with_full_content(top_articles)

    # Merge enriched back into full list
    enriched_urls = {a.get('url') for a in top_articles if a.get('url')}
    processed = top_articles + [a for a in processed[15:] if a.get('url') not in enriched_urls]
    processed = upsert_articles(processed)
    logger.info(f"Stage 2.5 (Firecrawl) completed in {time.time() - start_time:.2f}s.")

    # --- Stage 3: Generate --- (raises on failure → aborts pipeline)
    start_time = time.time()
    newsletter = generate_newsletter_all(processed, edition, db_path)
    logger.info(f"Stage 3 (Generate) completed in {time.time() - start_time:.2f}s.")

    # --- Stage 3.5: Extract IOCs and sync to shared Google Sheet ---
    start_time = time.time()
    # Article IOC extraction (now runs on full_content where available)
    processed_with_iocs = process_article_iocs(processed)
    article_iocs = get_all_unique_iocs(processed_with_iocs)

    # Parallel verified IOC feeds
    with ThreadPoolExecutor(max_workers=4) as executor:
        abuseipdb_future = executor.submit(fetch_abuseipdb_iocs)
        et_future = executor.submit(fetch_et_iocs)
        openphish_future = executor.submit(fetch_openphish_iocs)
        mallory_future = executor.submit(fetch_mallory_iocs)
        abuseipdb_iocs = abuseipdb_future.result()
        et_iocs = et_future.result()
        openphish_iocs = openphish_future.result()
        mallory_iocs = mallory_future.result()

    # Merge all streams
    all_iocs = abuseipdb_iocs + et_iocs + openphish_iocs + mallory_iocs + article_iocs

    logger.info(
        f"IOC streams merged: "
        f"{len(abuseipdb_iocs)} AbuseIPDB + "
        f"{len(et_iocs)} EmergingThreats + "
        f"{len(openphish_iocs)} OpenPhish + "
        f"{len(mallory_iocs)} Mallory + "
        f"{len(article_iocs)} article-extracted = "
        f"{len(all_iocs)} total"
    )

    from src.processor.ioc_tracker import track_and_filter_iocs
    filtered_iocs = track_and_filter_iocs(all_iocs, edition)

    # Mallory enrichment on the smaller, deduped/filtered set (minimizes API calls)
    enriched_iocs = enrich_iocs(filtered_iocs)

    # Sync to the shared Google Sheet — the Sheet is now the only durable IOC
    # store. On failure, sync_iocs() falls back to a local pending CSV that
    # gets retried and merged into the next run; never blocks the pipeline.
    sheet_synced = sync_iocs(enriched_iocs)

    logger.info(f"Stage 3.5 (IOCs) completed in {time.time() - start_time:.2f}s.")

    # --- Stage 4: Deliver ---
    start_time = time.time()
    if not dry_run:
        # Retry logic for delivery
        max_attempts = 3
        backoff = 60
        for attempt in range(max_attempts):
            try:
                recipient_override = [test_recipient] if test_recipient else None
                send_individual_emails(newsletter, attachment_content=None, attachment_filename=None, recipients_override=recipient_override)
                # Success! Record in DB
                selected_articles = newsletter.get('articles', [])
                record_newsletter(newsletter, edition, selected_articles, status='sent')
                logger.info(f"Stage 4 (Delivery) completed in {time.time() - start_time:.2f}s. Newsletter '{newsletter['subject']}' sent.")
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
        logger.debug(
            f"IOC sync {'succeeded' if sheet_synced else 'held locally pending retry'} "
            f"({len(enriched_iocs)} IOCs this run)."
        )
