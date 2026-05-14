# src/delivery/email_sender.py
import logging
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List
from src.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO

logger = logging.getLogger(__name__)

def send_individual_emails(newsletter: Dict):
    """
    Send the newsletter individually to each recipient in EMAIL_TO.
    V5 Enhancement: Loop through recipients for privacy and spam protection.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not set. Email delivery skipped.")
        return

    recipients = EMAIL_TO
    if not recipients:
        logger.warning("No recipients in EMAIL_TO. Delivery skipped.")
        return

    subject = newsletter.get('subject', 'GridPulse Newsletter')
    html_content = newsletter.get('content_html', '')
    text_content = newsletter.get('content_text', '')

    try:
        # Connect to SMTP server
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            
            for recipient in recipients:
                recipient = recipient.strip()
                if not recipient:
                    continue
                    
                logger.info(f"Sending newsletter to {recipient}")
                
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = EMAIL_FROM
                msg["To"] = recipient
                
                msg.attach(MIMEText(text_content, "plain"))
                msg.attach(MIMEText(html_content, "html"))
                
                try:
                    server.send_message(msg)
                    logger.debug(f"Successfully sent to {recipient}")
                except Exception as e:
                    logger.error(f"Failed to send to {recipient}: {e}")
                    # Continue to next recipient
                
                # Small delay to avoid triggering rate limits on some SMTP servers
                time.sleep(1)

    except Exception as e:
        logger.error(f"SMTP connection error: {e}")
        raise
