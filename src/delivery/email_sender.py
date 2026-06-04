# src/delivery/email_sender.py
import logging
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from src.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)

def send_individual_emails(newsletter: Dict, attachment_content: Optional[str] = None, attachment_filename: Optional[str] = None, recipients_override: Optional[List[str]] = None):
    """
    Send the newsletter individually to each recipient in EMAIL_TO.
    V5 Enhancement: Loop through recipients for privacy and spam protection.
    V5.3 Enhancement: Support for CSV attachments (IOCs).
    Test sends can pass recipients_override to avoid mailing production recipients.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not set. Email delivery skipped.")
        return

    recipients = recipients_override if recipients_override is not None else EMAIL_TO
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

                # Attach file if provided
                if attachment_content and attachment_filename:
                    part = MIMEApplication(attachment_content.encode('utf-8'), Name=attachment_filename)
                    part['Content-Disposition'] = f'attachment; filename="{attachment_filename}"'
                    msg.attach(part)

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
