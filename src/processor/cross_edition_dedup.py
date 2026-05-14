# src/processor/cross_edition_dedup.py
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from src.utils.datetime_utils import utc_now, dt_to_str

logger = logging.getLogger(__name__)

class CrossEditionDeduplicator:
    def __init__(self, db_path: str, reuse_window_days: int = 14):
        self.db_path = db_path
        self.reuse_window_days = reuse_window_days

    def _get_recently_used(self) -> tuple[set, set, set]:
        cutoff = dt_to_str(utc_now() - timedelta(days=self.reuse_window_days))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('PRAGMA journal_mode=WAL;') # V5 Enhancement
            cursor = conn.execute('''
                SELECT a.id, a.url, a.cve_id
                FROM articles a
                JOIN newsletter_articles na ON a.id = na.article_id
                JOIN newsletters n ON na.newsletter_id = n.id
                WHERE n.sent_date > ?
            ''', (cutoff,))
            rows = cursor.fetchall()

        used_ids = {r[0] for r in rows}
        used_urls = {r[1] for r in rows}
        used_cves = {r[2] for r in rows if r[2]}
        return used_ids, used_urls, used_cves

    def filter_candidates(self, articles: list[dict]) -> list[dict]:
        used_ids, used_urls, used_cves = self._get_recently_used()
        result = []
        for a in articles:
            if a.get('id') in used_ids:
                continue
            if a.get('url') in used_urls:
                continue
            if a.get('cve_id') and a['cve_id'] in used_cves:
                continue
            result.append(a)
        logger.debug(f"Cross-edition dedup: {len(articles)} → {len(result)} articles")
        return result
