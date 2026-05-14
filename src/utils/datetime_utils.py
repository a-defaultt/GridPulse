# src/utils/datetime_utils.py
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytz
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

def utc_now() -> datetime:
    """Return current UTC datetime (aware)."""
    return datetime.now(timezone.utc)

def to_utc(dt: datetime) -> datetime:
    """Convert naive (assumed UTC) or aware datetime to UTC-aware."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def dt_to_str(dt: datetime) -> str:
    """Serialize UTC datetime to consistent ISO 8601 string for SQLite storage."""
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def str_to_dt(s: Optional[str]) -> Optional[datetime]:
    """Deserialize ISO 8601 string from SQLite back to UTC-aware datetime."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        return to_utc(dt)
    except ValueError as e:
        logger.warning(f"Failed to parse stored datetime '{s}': {e}")
        return None

def to_timezone(dt: datetime, tz_name: str = "Africa/Tunis") -> datetime:
    """Convert UTC datetime to user's timezone for display only."""
    tz = pytz.timezone(tz_name)
    return dt.astimezone(tz)

def format_for_email(dt: datetime, tz_name: str = "Africa/Tunis") -> str:
    """Format datetime for email display."""
    local_dt = to_timezone(dt, tz_name)
    return local_dt.strftime("%A, %B %d, %Y at %I:%M %p %Z")

def parse_rss_date(date_str: str) -> Optional[datetime]:
    """
    Parse RSS feed date string to UTC-aware datetime.
    Returns None if unparseable — callers MUST use fetched_date as fallback.
    """
    if not date_str:
        return None

    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y %H:%M:%S %z",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return to_utc(dt)
        except ValueError:
            continue

    # Fallback: python-dateutil
    try:
        return to_utc(dateutil_parser.parse(date_str))
    except Exception as e:
        logger.warning(f"Unable to parse RSS date '{date_str}': {e}")
        return None  # Caller: use fetched_date as fallback
