import logging
import requests
from typing import Dict, Optional
from src.config import NVIDIA_TIMEOUT

logger = logging.getLogger(__name__)

def send_webhook_alert(webhook_url: str, newsletter: Dict, error_context: Optional[str] = None):
    """
    Sends a condensed high-severity alert payload to a secure Webhook.
    Used as an OOB failover when SMTP delivery fails.
    """
    if not webhook_url:
        logger.error("No Webhook URL provided for OOB fallback.")
        return

    subject = newsletter.get('subject', 'GridPulse OOB Alert')
    
    # Extract a few top items for the condensed payload
    # Note: We assume the newsletter might have 'articles' or we just use the subject/content
    summary = newsletter.get('content_text', '')[:1000] # First 1000 chars for context
    
    payload = {
        "text": f"[ALERT] GridPulse OOB Failover Alert [ALERT]\n\n"
                f"*Subject:* {subject}\n"
                f"*Status:* SMTP Primary Dispatch Failed\n"
                f"*Error:* {error_context or 'Unknown SMTP Error'}\n\n"
                f"*Summary (First 1000 chars):*\n{summary}\n\n"
                f"_Please check the GridPulse logs and primary mail server._"
    }

    try:
        logger.info(f"Attempting OOB Webhook failover to: {webhook_url}")
        response = requests.post(
            webhook_url, 
            json=payload, 
            timeout=NVIDIA_TIMEOUT or 30
        )
        response.raise_for_status()
        logger.info("OOB Webhook alert delivered successfully.")
    except Exception as e:
        logger.error(f"OOB Webhook failover FAILED: {e}")
