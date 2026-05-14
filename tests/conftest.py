# tests/conftest.py
import pytest
import sqlite3
import os
from pathlib import Path

# Fix: Use the correct path to schema.sql
SCHEMA_PATH = Path(__file__).parent.parent / 'database' / 'schema.sql'

@pytest.fixture
def db_path(tmp_path):
    db = tmp_path / "test.db"
    if not SCHEMA_PATH.exists():
         # Fallback if running from a different dir
         schema_file = Path("database/schema.sql")
         schema = schema_file.read_text()
    else:
        schema = SCHEMA_PATH.read_text()
        
    with sqlite3.connect(db) as conn:
        conn.executescript(schema)
    return str(db)

@pytest.fixture
def sources_yaml(tmp_path):
    yaml_content = """
rss_sources:
  - name: "Test Source"
    url: "https://example.com/feed.xml"
    type: rss
    enabled: true
    priority: 1
    topics: ["test"]
"""
    p = tmp_path / "sources.yaml"
    p.write_text(yaml_content)
    return str(p)
