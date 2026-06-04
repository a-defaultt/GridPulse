# src/processor/ai_deduplicator.py
# V5.2 Enhancement: Semantic deduplication using NVIDIA NIM embedding model.
# V5.4 Enhancement: Optimized with NumPy for large article sets.

import logging
import hashlib
from typing import List, Dict, Optional
import numpy as np

from openai import OpenAI
from src.config import NVIDIA_EMBEDDING_KEY, NVIDIA_KEYS, LLM_BASE_URL, NVIDIA_TIMEOUT, EMBEDDING_MODEL
from src.database.db_handler import get_ai_cache, set_ai_cache

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


def _get_cached_embeddings(texts: List[str]) -> tuple[List[np.ndarray | None], List[int]]:
    """Check cache for embeddings. Returns (results, missing_indices)."""
    results = []
    missing_indices = []
    for i, text in enumerate(texts):
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        cached_blob = get_ai_cache(text_hash, EMBEDDING_MODEL, 'embedding')
        if cached_blob:
            embedding = np.frombuffer(cached_blob, dtype=np.float32)
            results.append(embedding)
        else:
            results.append(None)
            missing_indices.append(i)
    return results, missing_indices


def semantic_deduplicate(articles: List[Dict]) -> List[Dict]:
    """
    Remove semantically similar articles using embedding cosine similarity.
    Uses SQLite cache to avoid redundant API calls.
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

    # Check cache
    all_embeddings_results, missing_indices = _get_cached_embeddings(texts)
    
    if missing_indices:
        logger.info(f"Generating embeddings for {len(missing_indices)} articles ({len(texts) - len(missing_indices)} cached)")
        texts_to_fetch = [texts[i] for i in missing_indices]
        
        # Generate embeddings in batches for missing ones
        batch_size = 50
        for i in range(0, len(texts_to_fetch), batch_size):
            batch_texts = texts_to_fetch[i:i + batch_size]
            batch_indices = missing_indices[i:i + batch_size]
            
            embeddings = _generate_embeddings(batch_texts, client)
            if embeddings is None:
                logger.warning("Embedding batch failed. Falling back — no semantic dedup for this run.")
                return articles
            
            # Store in cache and update results
            for j, emb in enumerate(embeddings):
                idx = batch_indices[j]
                text = batch_texts[j]
                text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
                
                # Ensure it's float32 for consistent BLOB storage
                emb_32 = emb.astype(np.float32)
                set_ai_cache(text_hash, "nvidia", EMBEDDING_MODEL, 'embedding', text, emb_32.tobytes())
                all_embeddings_results[idx] = emb_32
    else:
        logger.info(f"All {len(texts)} embeddings found in cache.")

    all_embeddings = np.vstack(all_embeddings_results)
    
    # Normalize vectors for cosine similarity
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
