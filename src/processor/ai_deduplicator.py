# src/processor/ai_deduplicator.py
# V5.2 Enhancement: Semantic deduplication using NVIDIA NIM embedding model.
# V5.4 Enhancement: Optimized with NumPy for large article sets.

import logging
from typing import List, Dict, Optional
import numpy as np

from openai import OpenAI
from src.config import NVIDIA_EMBEDDING_KEY, NVIDIA_KEYS, LLM_BASE_URL, NVIDIA_TIMEOUT, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Articles with cosine similarity >= this threshold are considered duplicates.
SIMILARITY_THRESHOLD = 0.85


def _get_embedding_client() -> Optional[OpenAI]:
    """Return an OpenAI client pointed at the NVIDIA NIM embedding endpoint."""
    key = NVIDIA_EMBEDDING_KEY or (NVIDIA_KEYS[0] if NVIDIA_KEYS else None)
    if not key:
        return None
    return OpenAI(base_url=LLM_BASE_URL, api_key=key, timeout=NVIDIA_TIMEOUT)


def _generate_embeddings(texts: List[str], client: OpenAI) -> Optional[np.ndarray]:
    """
    Call the NVIDIA NIM embedding API for a list of texts.
    Returns a NumPy array of embedding vectors, or None on failure.
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
        return np.array([item.embedding for item in sorted_data])
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None


def semantic_deduplicate(articles: List[Dict]) -> List[Dict]:
    """
    Remove semantically similar articles using embedding cosine similarity.
    Optimized using NumPy matrix operations for large datasets.
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

    # Limit semantic dedup to top articles to avoid excessive API costs/latency
    # even with numpy, 3700 articles is a lot of API calls.
    # Let's cap at 500 for now.
    MAX_ARTICLES = 500
    original_count = len(articles)
    if original_count > MAX_ARTICLES:
        logger.info(f"Capping semantic dedup to top {MAX_ARTICLES} articles (from {original_count})")
        articles_to_process = articles[:MAX_ARTICLES]
        remaining_articles = articles[MAX_ARTICLES:]
    else:
        articles_to_process = articles
        remaining_articles = []

    # Build a text representation for each article (title + truncated summary)
    texts = [
        f"{a.get('title', '')}. {a.get('summary', '')[:300]}"
        for a in articles_to_process
    ]

    # Generate embeddings in batches
    all_embeddings_list = []
    batch_size = 50
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = _generate_embeddings(batch, client)
        if embeddings is None:
            logger.warning("Embedding batch failed. Falling back — no semantic dedup for this run.")
            return articles
        all_embeddings_list.append(embeddings)

    all_embeddings = np.vstack(all_embeddings_list)
    
    # Normalize vectors for cosine similarity (dot product of normalized = cosine sim)
    norms = np.linalg.norm(all_embeddings, axis=1, keepdims=True)
    all_embeddings = all_embeddings / np.where(norms == 0, 1, norms)
    
    # Compute similarity matrix (N x N)
    sim_matrix = np.dot(all_embeddings, all_embeddings.T)

    # Mark duplicates
    is_duplicate = [False] * len(articles_to_process)
    duplicate_count = 0

    for i in range(len(articles_to_process)):
        if is_duplicate[i]:
            continue
        # Check all subsequent articles for similarity to article i
        # similarities are in the row i, columns i+1 to end
        similarities = sim_matrix[i, i+1:]
        duplicates = np.where(similarities >= SIMILARITY_THRESHOLD)[0]
        
        for dup_idx in duplicates:
            actual_idx = dup_idx + i + 1
            if not is_duplicate[actual_idx]:
                is_duplicate[actual_idx] = True
                duplicate_count += 1
                logger.debug(
                    f"Semantic duplicate (sim={sim_matrix[i, actual_idx]:.3f}): "
                    f"'{articles_to_process[actual_idx]['title']}' ≈ '{articles_to_process[i]['title']}'"
                )

    filtered_processed = [a for a, dup in zip(articles_to_process, is_duplicate) if not dup]
    result = filtered_processed + remaining_articles
    
    logger.info(
        f"Semantic dedup: {original_count} → {len(result)} articles "
        f"({duplicate_count} near-duplicates removed)"
    )
    return result
