# tests/test_datetime_utils.py
from datetime import datetime, timezone
from src.utils.datetime_utils import utc_now, dt_to_str, str_to_dt, parse_rss_date

def test_utc_now():
    now = utc_now()
    assert now.tzinfo == timezone.utc

def test_dt_serialization():
    dt = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
    s = dt_to_str(dt)
    assert s == "2026-05-14T12:00:00Z"
    
    dt2 = str_to_dt(s)
    assert dt2 == dt

def test_parse_rss_date():
    s = "Thu, 14 May 2026 12:00:00 +0000"
    dt = parse_rss_date(s)
    assert dt == datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
