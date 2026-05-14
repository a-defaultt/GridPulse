-- database/schema.sql — GridPulse V5 Final Schema

-- V5 Migration Strategy Tracking
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    url           TEXT    UNIQUE NOT NULL,
    source        TEXT    NOT NULL,
    source_type   TEXT    NOT NULL,
    published_date TEXT,                     -- ISO 8601 UTC string, nullable
    fetched_date   TEXT    NOT NULL,         -- ISO 8601 UTC string, set on insert
    summary        TEXT,
    content        TEXT,
    topics         TEXT,
    cvss_score     REAL,
    cve_id         TEXT,
    relevance_score REAL,
    is_processed   INTEGER DEFAULT 0        -- 0=unprocessed, 1=processed
);

CREATE TABLE IF NOT EXISTS newsletters (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    edition_type   TEXT    NOT NULL,         -- 'daily' | 'weekly' | 'monthly'
    edition_number INTEGER NOT NULL,
    subject        TEXT    NOT NULL,
    content_html   TEXT,
    content_text   TEXT,
    article_count  INTEGER DEFAULT 0,
    sent_date      TEXT    NOT NULL,         -- ISO 8601 UTC string
    status         TEXT    DEFAULT 'sent',   -- 'sent' | 'failed' | 'draft'
    UNIQUE(edition_type, edition_number)
);

CREATE TABLE IF NOT EXISTS newsletter_articles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id  INTEGER NOT NULL REFERENCES newsletters(id) ON DELETE CASCADE,
    article_id     INTEGER NOT NULL REFERENCES articles(id)    ON DELETE CASCADE,
    edition_type   TEXT    NOT NULL,
    edition_number INTEGER NOT NULL,
    position       INTEGER,
    is_featured    INTEGER DEFAULT 0,        -- 0=normal, 1=featured
    UNIQUE(article_id, edition_type, edition_number)
);

CREATE TABLE IF NOT EXISTS sources (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT    NOT NULL UNIQUE,
    url                  TEXT    NOT NULL,
    source_type          TEXT    NOT NULL,
    config_type          TEXT    NOT NULL,
    is_config_enabled    INTEGER DEFAULT 1,  -- mirrors sources.yaml enabled flag
    priority             INTEGER DEFAULT 1,
    topics               TEXT,
    last_fetched         TEXT,               -- ISO 8601 UTC string, nullable
    consecutive_failures INTEGER DEFAULT 0,
    last_error           TEXT,
    override_enabled     INTEGER DEFAULT 1   -- manual runtime override
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_articles_published  ON articles(published_date DESC);
CREATE INDEX IF NOT EXISTS idx_articles_cve         ON articles(cve_id);
CREATE INDEX IF NOT EXISTS idx_articles_source      ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_processed   ON articles(is_processed);
CREATE INDEX IF NOT EXISTS idx_newsletters_type     ON newsletters(edition_type, edition_number DESC);
CREATE INDEX IF NOT EXISTS idx_na_lookup            ON newsletter_articles(edition_type, edition_number);
CREATE INDEX IF NOT EXISTS idx_na_article           ON newsletter_articles(article_id);
