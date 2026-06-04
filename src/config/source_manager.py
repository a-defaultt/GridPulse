# src/config/source_manager.py
import os
import sqlite3
import yaml
import logging
from pathlib import Path
from typing import Optional
from src.utils.datetime_utils import utc_now, dt_to_str, str_to_dt

logger = logging.getLogger(__name__)

class SourceManager:
    """
    Manages content sources.
    IMPORTANT: Instantiate ONCE at application startup. Do not create per-fetch.

    Design:
    - sources.yaml: Version-controlled config
    - sources DB table: Runtime state (last_fetched, failures)
    """

    def __init__(self, yaml_path: str, db_path: str):
        self.yaml_path = Path(yaml_path)
        self.db_path = db_path
        self._yaml_sources: dict = {}
        self._load_yaml()
        self._init_db()
        self._sync_config_to_db()

    def _get_conn(self):
        """V5 Enhancement: Return a connection with WAL enabled for concurrency"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute('PRAGMA journal_mode=WAL;')
        return conn

    def _load_yaml(self):
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"sources.yaml not found: {self.yaml_path}")
        with open(self.yaml_path) as f:
            config = yaml.safe_load(f)
        self._yaml_sources = {}
        for config_type, key in [('rss', 'rss_sources'), ('api', 'api_sources'),
                                   ('vendor', 'vendor_sources'), ('community', 'community_sources')]:
            data = config.get(key, [])
            # Handle both list and dictionary formats
            if isinstance(data, dict):
                for name, src in data.items():
                    src['config_type'] = config_type
                    # Ensure name is in the dict
                    if 'name' not in src:
                        src['name'] = name
                    self._yaml_sources[src['name']] = src
            elif isinstance(data, list):
                for src in data:
                    src['config_type'] = config_type
                    self._yaml_sources[src['name']] = src

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    config_type TEXT NOT NULL,
                    is_config_enabled INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 1,
                    topics TEXT,
                    last_fetched TEXT,
                    consecutive_failures INTEGER DEFAULT 0,
                    last_error TEXT,
                    override_enabled INTEGER DEFAULT 1
                )
            ''')

    def _sync_config_to_db(self):
        yaml_names = set(self._yaml_sources.keys())
        with self._get_conn() as conn:
            for name, src in self._yaml_sources.items():
                exists = conn.execute('SELECT 1 FROM sources WHERE name = ?', (name,)).fetchone()
                config_enabled = 1 if src.get('enabled', True) else 0
                topics_str = ','.join(src.get('topics', []))
                if not exists:
                    conn.execute('''
                        INSERT INTO sources
                        (name, url, source_type, config_type, is_config_enabled, priority, topics)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        name, src['url'],
                        src.get('type', src.get('config_type', 'unknown')),
                        src['config_type'], config_enabled,
                        src.get('priority', 1), topics_str
                    ))
                else:
                    conn.execute('''
                        UPDATE sources SET is_config_enabled = ?, url = ?
                        WHERE name = ?
                    ''', (config_enabled, src['url'], name))

            if yaml_names:
                placeholders = ','.join('?' * len(yaml_names))
                conn.execute(
                    f'UPDATE sources SET is_config_enabled = 0 WHERE name NOT IN ({placeholders})',
                    list(yaml_names)
                )

    def get_enabled_sources(self) -> list[dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            # V5.7: Backoff — skip sources with > 5 consecutive failures
            cursor = conn.execute('''
                SELECT * FROM sources
                WHERE is_config_enabled = 1
                AND COALESCE(override_enabled, 0) = 1
                AND consecutive_failures < 5
                ORDER BY priority DESC, name ASC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def mark_fetched(self, name: str, success: bool,
                     error: Optional[str] = None, articles_count: int = 0,
                     etag: Optional[str] = None, last_modified: Optional[str] = None):
        now_str = dt_to_str(utc_now())
        with self._get_conn() as conn:
            if success:
                conn.execute('''
                    UPDATE sources SET 
                        last_fetched = ?, 
                        consecutive_failures = 0, 
                        last_error = NULL,
                        etag = COALESCE(?, etag),
                        last_modified = COALESCE(?, last_modified)
                    WHERE name = ?
                ''', (now_str, etag, last_modified, name))
                logger.info(f"Source '{name}': {articles_count} articles fetched")
            else:
                conn.execute('''
                    UPDATE sources
                    SET last_fetched = ?, consecutive_failures = consecutive_failures + 1, last_error = ?
                    WHERE name = ?
                ''', (now_str, error, name))
                logger.warning(f"Source '{name}' failed: {error}")
