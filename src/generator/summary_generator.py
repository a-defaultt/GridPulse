# src/generator/summary_generator.py
import logging
import json
import hashlib
from typing import List, Dict
from openai import OpenAI
from src.config import LLM_BASE_URL, NVIDIA_SUMMARIZER_KEY, NVIDIA_KEYS, LLM_MODEL, NVIDIA_TIMEOUT
from src.database.db_handler import get_ai_cache, set_ai_cache
from src.utils.sanitizer import sanitize_content, wrap_with_delimiters, get_injection_instruction

logger = logging.getLogger(__name__)

def generate_summaries_batch(articles: List[Dict]) -> List[Dict]:
    """
    Generate summaries for articles in batches of 10 using LLM.
    Uses SQLite cache to avoid redundant summarization.
    """
    if not articles:
        return articles

    # V5.7: Check cache first
    missing_articles = []
    for a in articles:
        input_text = f"{a.get('title', '')}. {a.get('summary', '')[:500]}"
        text_hash = hashlib.sha256(input_text.encode('utf-8')).hexdigest()
        cached = get_ai_cache(text_hash, LLM_MODEL, 'summary')
        if cached:
            a['llm_summary'] = cached.decode('utf-8')
        else:
            missing_articles.append(a)

    if not missing_articles:
        logger.info("All summaries found in cache.")
        return articles

    logger.info(f"Generating LLM summaries for {len(missing_articles)} articles ({len(articles) - len(missing_articles)} cached)")

    # Build local key list
    local_keys = list(dict.fromkeys(
        [NVIDIA_SUMMARIZER_KEY] + NVIDIA_KEYS
    )) if NVIDIA_SUMMARIZER_KEY else NVIDIA_KEYS

    if not local_keys:
        logger.warning("No LLM API keys found. Skipping remaining LLM summaries.")
        return articles

    batch_size = 10
    current_key_index = 0
    
    for i in range(0, len(missing_articles), batch_size):
        batch = missing_articles[i:i + batch_size]
        logger.info(f"Batch {i//batch_size + 1}/{len(missing_articles)//batch_size + 1}")
        
        # Prepare prompt - Sanitize input
        prompt_data = [
            {
                "id": j, 
                "title": sanitize_content(a.get('title', '')), 
                "summary": sanitize_content(a.get('summary', ''), max_chars=1000)
            } 
            for j, a in enumerate(batch)
        ]
        
        system_prompt = (
            "You are a cybersecurity expert. Summarize the following news items for a professional newsletter. "
            "Keep each summary to 2-3 concise sentences focusing on the impact and recommended action. "
            "Respond ONLY with a JSON list of objects, each containing 'id' and 'summary'.\n\n"
            f"{get_injection_instruction()}"
        )
        
        # Wrap data in delimiters
        raw_content = wrap_with_delimiters(json.dumps(prompt_data))
        
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
                        {"role": "user", "content": raw_content}
                    ],
                    response_format={"type": "json_object"} if "llama3" not in LLM_MODEL.lower() else None
                )
                
                content = response.choices[0].message.content
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
                        summary_text = s.get('summary')
                        batch[idx]['llm_summary'] = summary_text
                        
                        # Cache it
                        a = batch[idx]
                        input_text = f"{a.get('title', '')}. {a.get('summary', '')[:500]}"
                        text_hash = hashlib.sha256(input_text.encode('utf-8')).hexdigest()
                        set_ai_cache(text_hash, "nvidia", LLM_MODEL, 'summary', input_text, summary_text.encode('utf-8'))
                
                success = True
                
            except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    logger.warning(f"Rate limit hit for key {current_key_index + 1}. Rotating.")
                    current_key_index = (current_key_index + 1) % len(local_keys)
                    attempts_with_keys += 1
                else:
                    logger.error(f"LLM batch summary generation failed: {e}")
                    break
                    
    return articles
