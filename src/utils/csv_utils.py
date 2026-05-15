# src/utils/csv_utils.py
import csv
import io
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def generate_ioc_csv(iocs: List[Dict]) -> str:
    """
    Generate a CSV string from a list of IOC dictionaries.
    """
    if not iocs:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['type', 'value', 'source_article', 'source_url'])
    writer.writeheader()
    for ioc in iocs:
        # Ensure we only write expected fields
        row = {
            'type': ioc.get('type'),
            'value': ioc.get('value'),
            'source_article': ioc.get('source_article', 'N/A'),
            'source_url': ioc.get('source_url', 'N/A')
        }
        writer.writerow(row)
    
    return output.getvalue()
