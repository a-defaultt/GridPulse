# src/processor/ai_deduplicator.py
# V5.2 Enhancement: Semantic deduplication using NVIDIA NIM embedding model.
# Catches near-duplicate articles that exact URL/title matching misses
# (e.g. "Microsoft Patches Critical RCE" ≈ "Critical Remote Code Execution Fixed in Windows").

import math
import logging
from typing import List, Dict, Optional

from openai import OpenAI
from src.config import NVIDIA_KEYS, LLM_BASE_URL, NVIDIA_TIMEOUT, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Articles with cosine similarity >= this threshold are considered duplicates.
SIMILARITY_THRESHOLD = 0.85


def _get_embedding_client() -> Optional[OpenAI]:
    """Return an OpenAI client pointed at the NVIDIA NIM embedding endpoint."""
    if not NVIDIA_KEYS:
        return None
    return OpenAI(base_url=LLM_BASE_URL, api_key=NVIDIA_KEYS[0], timeout=NVIDIA_TIMEOUT)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors using stdlib math."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _generate_embeddings(texts: List[str], client: OpenAI) -> Optional[List[List[float]]]:
    """
    Call the NVIDIA NIM embedding API for a list of texts.
    Returns a list of embedding vectors, or None on failure.
    """
    try:
        response = client.embeddings.create(
            input=texts,
            model=EMBEDDING_MODEL,
            encoding_format="float",
            extra_body={"input_type": "passage", "truncate": "END"}
        )
        # Sort by index to guarantee order matches input order
        sorted_data = sorted(response.data, key=lambda d: d.index)
        return [item.embedding for item in sorted_data]
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None


def semantic_deduplicate(articles: List[Dict]) -> List[Dict]:
    """
    Remove semantically similar articles using embedding cosine similarity.
    When two articles are too similar, the one that appeared later in the
    list is dropped (the first one — typically from a higher-priority source
    — is kept).

    Falls back gracefully: if the embedding API is unavailable the original
    list is returned unchanged.
    """
    if len(articles) < 2:
        return articles

    client = _get_embedding_client()
    if not client:
        logger.warning("No API keys available for embeddings. Skipping semantic dedup.")
        return articles

    if not EMBEDDING_MODEL:
        logger.warning("EMBEDDING_MODEL not configured. Skipping semantic dedup.")
        return articles

    # Build a text representation for each article (title + truncated summary)
    texts = [
        f"{a.get('title', '')}. {a.get('summary', '')[:300]}"
        for a in articles
    ]

    # Generate embeddings in batches (NVIDIA NIM limit ~96 inputs per call)
    all_embeddings: List[List[float]] = []
    batch_size = 50
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = _generate_embeddings(batch, client)
        if embeddings is None:
            logger.warning("Embedding batch failed. Falling back — no semantic dedup for this run.")
            return articles
        all_embeddings.extend(embeddings)

    # Pairwise similarity — mark later duplicates for removal
    is_duplicate = [False] * len(articles)
    duplicate_count = 0

    for i in range(len(articles)):
        if is_duplicate[i]:
            continue
        for j in range(i + 1, len(articles)):
            if is_duplicate[j]:
                continue
            sim = _cosine_similarity(all_embeddings[i], all_embeddings[j])
            if sim >= SIMILARITY_THRESHOLD:
                is_duplicate[j] = True
                duplicate_count += 1
                logger.debug(
                    f"Semantic duplicate (sim={sim:.3f}): "
                    f"'{articles[j]['title']}' ≈ '{articles[i]['title']}'"
                )

    result = [a for a, dup in zip(articles, is_duplicate) if not dup]
    logger.info(
        f"Semantic dedup: {len(articles)} → {len(result)} articles "
        f"({duplicate_count} near-duplicates removed)"
    )
    return result
