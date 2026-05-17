# src/processor/ioc_extractor.py
"""
IOC Extractor — Regex-based Indicator of Compromise extraction.
V5.5: Now operates on `full_content` (Firecrawl-fetched markdown)
when available. Falls back to `summary` for non-crawled articles,
and tags the extraction source so the CSV can distinguish quality tiers.

IOC types extracted:
  - IPv4 addresses (RFC-1918 private ranges excluded)
  - Domains (heuristic TLD allowlist applied)
  - MD5 / SHA1 / SHA256 file hashes
"""

import re
import logging
from typing import List, Dict, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Excludes private/loopback ranges (10.x, 192.168.x, 172.16-31.x, 127.x)
_RE_IP = re.compile(
    r"\b(?!10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|127\.)"
    r"(?:\d{1,3}\.){3}\d{1,3}\b"
)

# Domain: letters/digits/hyphens, dot-separated, ends with a known TLD
_COMMON_TLDS = r"(?:com|net|org|io|gov|edu|mil|info|biz|ru|cn|ir|kp|xyz|onion|zip)"
_RE_DOMAIN = re.compile(
    rf"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{{0,61}}[a-zA-Z0-9])?\.)+{_COMMON_TLDS}\b",
    re.IGNORECASE,
)

_RE_MD5    = re.compile(r"\b[a-fA-F0-9]{32}\b")
_RE_SHA1   = re.compile(r"\b[a-fA-F0-9]{40}\b")
_RE_SHA256 = re.compile(r"\b[a-fA-F0-9]{64}\b")

# ---------------------------------------------------------------------------
# Domain noise filter — skip generic words that match the domain pattern
# ---------------------------------------------------------------------------
_DOMAIN_BLOCKLIST = {
    "example.com", "localhost.com", "test.com", "sample.com",
    "your-domain.com", "domain.com", "email.com",
}


def extract_iocs(text: str) -> List[Dict[str, str]]:
    """
    Extract Indicators of Compromise (IOCs) from text using regex.
    Returns a list of unique IOC dictionaries.
    """
    if not text:
        return []

    found_iocs = []
    seen = set()

    # --- Hashes first (most specific — extract before IP/domain pass) ------
    # SHA256
    sha256_matches = set()
    for match in _RE_SHA256.finditer(text):
        val = match.group()
        sha256_matches.add(val)
        if ('sha256', val) not in seen:
            found_iocs.append({'type': 'sha256', 'value': val})
            seen.add(('sha256', val))

    # SHA1 — only match strings NOT already captured as SHA256
    sha1_matches = set()
    for match in _RE_SHA1.finditer(text):
        val = match.group()
        sha1_matches.add(val)
        if val not in sha256_matches and ('sha1', val) not in seen:
            found_iocs.append({'type': 'sha1', 'value': val})
            seen.add(('sha1', val))

    # MD5 — reject if it's a substring of a longer hash match
    for match in _RE_MD5.finditer(text):
        val = match.group()
        if val not in sha256_matches and val not in sha1_matches and ('md5', val) not in seen:
            found_iocs.append({'type': 'md5', 'value': val})
            seen.add(('md5', val))

    # --- IP addresses -------------------------------------------------------
    for match in _RE_IP.finditer(text):
        val = match.group()
        # Basic validity: all octets <= 255
        if all(int(o) <= 255 for o in val.split(".")):
            if ('ip_address', val) not in seen:
                found_iocs.append({'type': 'ip_address', 'value': val})
                seen.add(('ip_address', val))

    # --- Domains ------------------------------------------------------------
    for match in _RE_DOMAIN.finditer(text):
        val = match.group().lower()
        if val not in _DOMAIN_BLOCKLIST and ('domain', val) not in seen:
            found_iocs.append({'type': 'domain', 'value': val})
            seen.add(('domain', val))

    return found_iocs


def process_article_iocs(articles: List[Dict]) -> List[Dict]:
    """
    Extract IOCs from a list of articles and associate them with each article.

    V5.5: Uses `full_content` (Firecrawl markdown) when available,
    otherwise falls back to `summary`. Tags the extraction source.
    """
    for a in articles:
        # Select text source and tag quality
        if a.get('full_content'):
            text_to_scan = f"{a['title']} {a['full_content']}"
            a['extraction_source'] = 'full_content'
        else:
            text_to_scan = f"{a['title']} {a['summary']} {a.get('content', '')}"
            a['extraction_source'] = 'summary_fallback'

        a['iocs'] = extract_iocs(text_to_scan)
    return articles


def get_all_unique_iocs(articles: List[Dict]) -> List[Dict]:
    """
    Aggregate all unique IOCs from a list of articles.
    """
    all_iocs = []
    seen = set()
    for a in articles:
        for ioc in a.get('iocs', []):
            key = (ioc['type'], ioc['value'])
            if key not in seen:
                # Add source info
                ioc_entry = ioc.copy()
                ioc_entry['source'] = 'article_extraction'
                ioc_entry['article_title'] = a['title']
                ioc_entry['linked_article'] = a.get('url', 'N/A')
                ioc_entry['extraction_source'] = a.get('extraction_source', 'unknown')
                all_iocs.append(ioc_entry)
                seen.add(key)
    return all_iocs
