import requests
from src.config import LLM_BASE_URL, NVIDIA_RERANKER_KEY, NVIDIA_TIMEOUT, RERANKER_MODEL

def debug_reranker():
    # Attempting to find the correct reranker endpoint
    base_url = LLM_BASE_URL.rstrip('/')
    endpoints = [
        f"{base_url}/ranking",
        f"{base_url}/v1/ranking",
        f"{base_url}/retrieval/reranking"
    ]
    
    headers = {
        "Authorization": f"Bearer {NVIDIA_RERANKER_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": RERANKER_MODEL,
        "query": {"text": "test"},
        "passages": [{"text": "test"}]
    }

    for url in endpoints:
        print(f"Testing Reranker Endpoint: {url}")
        try:
            response = requests.post(url, headers=headers, json=data, timeout=NVIDIA_TIMEOUT)
            print(f"Status: {response.status_code}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    debug_reranker()
