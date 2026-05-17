# src/utils/csv_utils.py
"""
IOC CSV generation helpers.
V5.5: Supports merged IOC streams from article extraction, ThreatFox, and OTX.
The `source` column distinguishes origin; `extraction_source` and `confidence`
columns let analysts filter the CSV by quality tier.
"""
import csv
import io
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def generate_ioc_csv(iocs: List[Dict]) -> str:
    """
    Generate a CSV string from a list of IOC dictionaries.
    Supports both article-extracted IOCs and threat-feed IOCs (ThreatFox/OTX).
    """
    if not iocs:
        return ""

    CSV_COLUMNS = [
        "type",
        "value",
        "source",             # "article_extraction" | "ThreatFox" | "OTX"
        "confidence",
        "malware_family",
        "threat_type",
        "source_article",     # article title
        "source_url",         # article URL
        "extraction_source",  # "full_content" | "summary_fallback"
    ]

    FIELD_MAP = {
        "type":              "ioc_type",
        "value":             "ioc_value",
        "source":            "source",            
        "confidence":        "confidence",
        "malware_family":    "malware_family",
        "threat_type":       "threat_type",
        "source_article":    "article_title",     
        "source_url":        "linked_article",    
        "extraction_source": "extraction_source",
    }

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction='ignore')
    writer.writeheader()

    for ioc in iocs:
        row = {}
        for col, key in FIELD_MAP.items():
            # Support both 'type'/'value' and 'ioc_type'/'ioc_value'
            if col == 'type':
                row[col] = ioc.get('type') or ioc.get('ioc_type', '')
            elif col == 'value':
                row[col] = ioc.get('value') or ioc.get('ioc_value', '')
            else:
                row[col] = ioc.get(key, '')
                
        # Ensure we always have a source
        if not row['source']:
            row['source'] = 'article_extraction' if ioc.get('article_title') else 'Unknown'
            
        writer.writerow(row)

    return output.getvalue()
