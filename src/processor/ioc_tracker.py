import sqlite3
import logging
from typing import List, Dict
from datetime import timedelta
from src.config import DATABASE_PATH
from src.utils.datetime_utils import utc_now, dt_to_str

logger = logging.getLogger(__name__)

def track_and_filter_iocs(iocs: List[Dict], edition: str) -> List[Dict]:
    """
    Saves new IOCs to the database and filters out old ones based on the edition type.
    - daily: returns IOCs first seen in the last 24 hours.
    - weekly: returns IOCs first seen in the last 7 days.
    - monthly: returns IOCs first seen in the last 30 days.
    """
    if not iocs:
        return []

    now = utc_now()
    now_str = dt_to_str(now)

    if edition == 'daily':
        cutoff = now - timedelta(days=1)
    elif edition == 'weekly':
        cutoff = now - timedelta(days=7)
    elif edition == 'monthly':
        cutoff = now - timedelta(days=30)
    else:
        cutoff = now - timedelta(days=365)
        
    cutoff_str = dt_to_str(cutoff)
    filtered_iocs = []
    
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10.0) as conn:
            conn.execute('PRAGMA journal_mode=WAL;')
            
            # Use executemany for fast inserts
            insert_data = []
            valid_iocs = []
            for ioc in iocs:
                val = ioc.get('ioc_value') or ioc.get('value')
                typ = ioc.get('ioc_type') or ioc.get('type')
                src = ioc.get('source', 'Unknown')
                if val and typ:
                    # Treat domains/urls case-insensitively for dedup if appropriate, but let's just stick to exact match
                    insert_data.append((val, typ, src, now_str))
                    valid_iocs.append(ioc)
                    
            if insert_data:
                conn.executemany('''
                    INSERT OR IGNORE INTO iocs (ioc_value, ioc_type, source, first_seen)
                    VALUES (?, ?, ?, ?)
                ''', insert_data)
                
                # Fetch all recent IOC keys from the DB
                # This is fast because we have an index on first_seen
                cursor = conn.execute('''
                    SELECT ioc_value, ioc_type FROM iocs
                    WHERE first_seen >= ?
                ''', (cutoff_str,))
                
                recent_keys = {(row[0], row[1]) for row in cursor.fetchall()}
                
                # Keep only IOCs that are in the recent_keys set
                for ioc in valid_iocs:
                    val = ioc.get('ioc_value') or ioc.get('value')
                    typ = ioc.get('ioc_type') or ioc.get('type')
                    if (val, typ) in recent_keys:
                        filtered_iocs.append(ioc)
                        
    except Exception as e:
        logger.error(f"Error tracking IOCs: {e}")
        # Fail open: if DB fails, return all IOCs so we don't send an empty CSV
        return iocs
        
    logger.info(f"IOC deduplication ({edition}): {len(iocs)} total fetched -> {len(filtered_iocs)} kept (first seen >= {cutoff_str})")
    return filtered_iocs
