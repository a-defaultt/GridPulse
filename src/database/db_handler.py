# src/database/db_handler.py
import sqlite3
import logging
from pathlib import Path
from src.config import DATABASE_PATH, BASE_DIR

logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL;')
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
