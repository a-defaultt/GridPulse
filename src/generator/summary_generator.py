# src/generator/summary_generator.py
import logging
import json
from typing import List, Dict
from openai import OpenAI
from src.config import LLM_BASE_URL, NVIDIA_SUMMARIZER_KEY, NVIDIA_KEYS, LLM_MODEL, NVIDIA_TIMEOUT

logger = logging.getLogger(__name__)

def generate_summaries_batch(articles: List[Dict]) -> List[Dict]:
    """
    Generate summaries for articles in batches of 10 using LLM.
    V5 Enhancement: Uses OpenAI client and JSON batch prompting.
    V5.1 Enhancement: Multi-key rotation for NVIDIA free tier limits.
    V5.2 Enhancement: Uses dedicated NVIDIA_SUMMARIZER_KEY.
    """
    # Build local key list: dedicated summarizer key first, then rotation pool
    local_keys = list(dict.fromkeys(
        [NVIDIA_SUMMARIZER_KEY] + NVIDIA_KEYS
    )) if NVIDIA_SUMMARIZER_KEY else NVIDIA_KEYS

    if not local_keys:
        logger.warning("No LLM API keys found. Skipping LLM summaries.")
        return articles

    batch_size = 10
    current_key_index = 0
    
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        logger.info(f"Generating LLM summaries for batch {i//batch_size + 1} ({len(batch)} articles)")
        
        # Prepare prompt
        prompt_data = [
            {"id": j, "title": a['title'], "summary": a['summary'][:500]} 
            for j, a in enumerate(batch)
        ]
        
        system_prompt = (
            "You are a cybersecurity expert. Summarize the following news items for a professional newsletter. "
            "Keep each summary to 2-3 concise sentences focusing on the impact and recommended action. "
            "Respond ONLY with a JSON list of objects, each containing 'id' and 'summary'."
        )
        
        success = False
        attempts_with_keys = 0
        
        while not success and attempts_with_keys < len(local_keys):
            api_key = local_keys[current_key_index]
            client = OpenAI(base_url=LLM_BASE_URL, api_key=api_key, timeout=NVIDIA_TIMEOUT)
            
            try:
                response = client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(prompt_data)}
                    ],
                    response_format={"type": "json_object"} if "llama3" not in LLM_MODEL.lower() else None
                )
                
                content = response.choices[0].message.content
                # ... same parsing logic as before ...
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0].strip()
                elif '```' in content:
                    content = content.split('```')[1].split('```')[0].strip()
                    
                summaries = json.loads(content)
                if isinstance(summaries, dict):
                    for val in summaries.values():
                        if isinstance(val, list):
                            summaries = val
                            break
                
                for s in summaries:
                    idx = s.get('id')
                    if isinstance(idx, int) and idx < len(batch):
                        batch[idx]['llm_summary'] = s.get('summary')
                
                success = True
                
            except Exception as e:
                # Check for rate limit (429)
                if "429" in str(e) or "rate limit" in str(e).lower():
                    logger.warning(f"Rate limit hit for key {current_key_index + 1}. Rotating to next key.")
                    current_key_index = (current_key_index + 1) % len(local_keys)
                    attempts_with_keys += 1
                else:
                    logger.error(f"LLM batch summary generation failed: {e}")
                    break # Other errors abort this batch
                    
    return articles
