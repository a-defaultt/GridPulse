# src/processor/ai_categorizer.py
# V5.2 Enhancement: LLM-powered article categorization using NVIDIA NIM.
# Enriches the existing keyword-based categories with nuanced, context-aware
# multi-label classification — catching categories that simple regex misses.

import json
import logging
from typing import List, Dict

from openai import OpenAI
from src.config import NVIDIA_CATEGORIZER_KEY, NVIDIA_KEYS, LLM_BASE_URL, NVIDIA_TIMEOUT, CATEGORIZER_MODEL
from src.utils.sanitizer import sanitize_content, wrap_with_delimiters, get_injection_instruction

logger = logging.getLogger(__name__)

CATEGORIES = [
    "vulnerability", "ransomware", "malware", "data-breach",
    "state-sponsored", "phishing", "supply-chain", "zero-day",
    "patch-update", "regulatory", "insider-threat", "iot-ot",
    "cloud-security", "tools", "general",
]

def _safe_parse_json(text: str):
    """
    Extracts the first valid JSON object/array from LLM output.
    Handles: trailing garbage, concatenated objects, markdown fences.
    """
    text = text.strip().replace("```json", "").replace("```", "").strip()
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(text)   # stops after first complete object/array
        return obj
    except json.JSONDecodeError:
        # Last resort: find the first complete bracket pair
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start = text.find(start_char)
            end   = text.rfind(end_char)
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except json.JSONDecodeError:
                    continue
        raise   # give up, let the caller handle it




def ai_categorize_batch(articles: List[Dict]) -> List[Dict]:
    """
    Send articles to an LLM in batches for multi-label categorization
    and CVE extraction.  Results are *merged* with any categories already
    assigned by the keyword categorizer so nothing is lost.

    Falls back gracefully: on any failure the articles are returned with
    their existing keyword-based categories intact.
    """
    primary_key = NVIDIA_CATEGORIZER_KEY or (NVIDIA_KEYS[0] if NVIDIA_KEYS else None)
    if not primary_key:
        logger.warning("No API keys available. Skipping AI categorization.")
        return articles

    if not CATEGORIZER_MODEL:
        logger.warning("CATEGORIZER_MODEL not configured. Skipping AI categorization.")
        return articles

    batch_size = 15  # Keep batches small for the 8B model
    current_key_index = 0
    # Build a local key list: dedicated key first, then the rotation pool
    local_keys = list(dict.fromkeys([primary_key] + NVIDIA_KEYS))
    client = OpenAI(
        base_url=LLM_BASE_URL,
        api_key=local_keys[current_key_index],
        timeout=NVIDIA_TIMEOUT,
    )

    system_prompt = (
        "You are a cybersecurity analyst. Classify each article into one or more "
        f"categories from this list: {json.dumps(CATEGORIES)}. "
        "Also extract any CVE IDs (format: CVE-YYYY-NNNNN) mentioned in the title or summary. "
        "Respond ONLY with a JSON array of objects, one per article: "
        '[{"id": 0, "categories": ["cat1", "cat2"], "cves": ["CVE-..."]}]. '
        "If no CVEs are found, return an empty list for cves.\n\n"
        f"{get_injection_instruction()}"
    )

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]

        prompt_data = [
            {
                "id": j,
                "title": sanitize_content(a.get("title", "")),
                "summary": sanitize_content(a.get("summary", ""), max_chars=800),
            }
            for j, a in enumerate(batch)
        ]
        
        # Wrap data in delimiters
        raw_content = wrap_with_delimiters(json.dumps(prompt_data))

        success = False
        attempts_with_keys = 0

        while not success and attempts_with_keys < len(local_keys):
            try:
                response = client.chat.completions.create(
                    model=CATEGORIZER_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": raw_content},
                    ],
                    temperature=0.1,  # Low temperature for deterministic classification
                )

                content = response.choices[0].message.content
                results = _safe_parse_json(content)

                # Handle dict-wrapped responses (some models wrap in {"results": [...]})
                if isinstance(results, dict):
                    for val in results.values():
                        if isinstance(val, list):
                            results = val
                            break

                # Merge AI categories into existing keyword categories
                for r in results:
                    idx = r.get("id")
                    if not isinstance(idx, int) or idx >= len(batch):
                        continue

                    ai_cats = r.get("categories", [])
                    ai_cves = r.get("cves", [])

                    # Merge categories (union of keyword + AI)
                    if ai_cats:
                        existing = (
                            set(batch[idx].get("topics", "").split(","))
                            if batch[idx].get("topics")
                            else set()
                        )
                        existing.update(c for c in ai_cats if c in CATEGORIES)
                        batch[idx]["topics"] = ",".join(filter(None, existing))

                    # Set CVE if not already present
                    if ai_cves and not batch[idx].get("cve_id"):
                        batch[idx]["cve_id"] = ai_cves[0].upper()

                success = True
                logger.debug(
                    f"AI categorization batch {i // batch_size + 1}: "
                    f"{len(batch)} articles classified"
                )

            except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    logger.warning(
                        f"Rate limit on key {current_key_index + 1}. "
                        f"Rotating to next key."
                    )
                    current_key_index = (current_key_index + 1) % len(local_keys)
                    client = OpenAI(
                        base_url=LLM_BASE_URL,
                        api_key=local_keys[current_key_index],
                        timeout=NVIDIA_TIMEOUT,
                    )
                    attempts_with_keys += 1
                else:
                    logger.error(f"AI categorization batch failed: {e}")
                    break  # Skip this batch, keyword categories are still present

    logger.info(f"AI categorization complete for {len(articles)} articles")
    return articles
