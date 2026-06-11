# src/processor/ai_ranker.py
# V5.2 Enhancement: Neural reranking using NVIDIA NIM reranker model.
# Uses a neural passage-reranker to score how relevant each article is to
# a cybersecurity audience, then blends the neural score with the existing
# heuristic score for a combined ranking.

import logging
from typing import List, Dict

import requests as http_requests  # Alias to avoid clash with any local names
from src.config import NVIDIA_RERANKER_KEY, NVIDIA_KEYS, LLM_BASE_URL, NVIDIA_TIMEOUT, RERANKER_MODEL
from src.utils.sanitizer import sanitize_content

logger = logging.getLogger(__name__)

# The query that defines "what matters" for reranking.
# The reranker scores each article's relevance to this query.
RERANK_QUERY = (
    "Critical cybersecurity threats, actively exploited vulnerabilities, "
    "ransomware campaigns, and security incidents requiring immediate "
    "attention from security professionals and SOC teams"
)

# Weight split: how much of the final score comes from each signal
HEURISTIC_WEIGHT = 0.4
NEURAL_WEIGHT = 0.6


def neural_rerank(articles: List[Dict]) -> List[Dict]:
    """
    Re-score and re-sort articles using the NVIDIA NIM reranker model.

    1. Sends article text to the ``/ranking`` endpoint.
    2. Normalises the raw logit scores to a 0-10 range.
    3. Blends with the existing heuristic ``relevance_score``
       (40 % heuristic + 60 % neural).
    4. Re-sorts articles by the combined score.

    Falls back gracefully: on any failure the heuristic-only ranking
    is preserved.
    """
    if not articles:
        return articles

    reranker_key = NVIDIA_RERANKER_KEY or (NVIDIA_KEYS[0] if NVIDIA_KEYS else None)
    if not reranker_key:
        logger.warning("No API keys available. Skipping neural reranking.")
        return articles

    if not RERANKER_MODEL:
        logger.warning("RERANKER_MODEL not configured. Skipping neural reranking.")
        return articles

    # Prepare passages (title + truncated summary for each article)
    passages = [
        {
            "text": f"{sanitize_content(a.get('title', ''))}. "
                    f"{sanitize_content(a.get('summary', ''), max_chars=500)}"
        }
        for a in articles
    ]

    # The reranker uses a dedicated NVIDIA retrieval/reranking endpoint
    # Pattern: {LLM_BASE_URL}/retrieval/nvidia/{model-name}/reranking
    # We strip the trailing 'v1' from LLM_BASE_URL if it exists to construct the path correctly.
    RERANKER_BASE_URL = "https://ai.api.nvidia.com/v1"
    api_url = f"{RERANKER_BASE_URL}/retrieval/nvidia/{RERANKER_MODEL.split('/')[-1]}/reranking"

    headers = {
        "Authorization": f"Bearer {reranker_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        # Process in batches of 50 (API limit per call)
        all_scores: Dict[int, float] = {}
        batch_size = 50

        for i in range(0, len(passages), batch_size):
            batch_passages = passages[i:i + batch_size]

            payload = {
                "model": RERANKER_MODEL,
                "query": {"text": RERANK_QUERY},
                "passages": batch_passages,
            }

            response = http_requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=NVIDIA_TIMEOUT,
            )
            response.raise_for_status()

            result = response.json()
            rankings = result.get("rankings", [])

            for r in rankings:
                # r["index"] is relative to this batch
                original_index = i + r["index"]
                all_scores[original_index] = r.get("logit", 0.0)

        if not all_scores:
            logger.warning("Reranker returned no scores. Keeping heuristic ranking.")
            return articles

        # Normalise neural scores to 0-10 range
        raw_values = list(all_scores.values())
        min_score = min(raw_values)
        max_score = max(raw_values)
        score_range = max_score - min_score if max_score != min_score else 1.0

        for idx, raw in all_scores.items():
            normalised = ((raw - min_score) / score_range) * 10.0
            articles[idx]["neural_score"] = round(normalised, 2)

            # Blend: weighted combination of heuristic + neural
            heuristic = articles[idx].get("relevance_score", 0.0)
            articles[idx]["relevance_score"] = round(
                HEURISTIC_WEIGHT * heuristic + NEURAL_WEIGHT * normalised, 2
            )

        # Re-sort by the blended score
        articles.sort(
            key=lambda x: x.get("relevance_score", 0), reverse=True
        )
        logger.info(f"Neural reranking applied to {len(articles)} articles")

    except http_requests.exceptions.HTTPError as e:
        logger.error(
            f"Neural reranking HTTP error ({e.response.status_code}): "
            f"{e.response.text[:200]}. Using heuristic scores only."
        )
    except Exception as e:
        logger.error(f"Neural reranking failed: {e}. Using heuristic scores only.")

    return articles
