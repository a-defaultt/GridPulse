# src/delivery/email_sender.py
import logging
import smtplib
import ssl
import time
import gnupg
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Dict, List, Optional
from src.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, 
    EMAIL_FROM, EMAIL_TO, GPG_HOME, GPG_PASSPHRASE, GPG_KEY_ID,
    OOB_WEBHOOK_URL
)
from src.delivery.webhook_sender import send_webhook_alert

logger = logging.getLogger(__name__)

def sign_payload(payload: str) -> str:
    """Signs a string payload using PGP."""
    if not GPG_KEY_ID:
        return payload
    
    gpg = gnupg.GPG(gnupghome=GPG_HOME)
    signed_data = gpg.sign(payload, keyid=GPG_KEY_ID, passphrase=GPG_PASSPHRASE, detach=False)
    
    if not signed_data.status == "signature created":
        logger.error(f"PGP Signing failed: {signed_data.stderr}")
        return payload
        
    return str(signed_data)

def send_individual_emails(newsletter: Dict, attachment_content: Optional[str] = None, attachment_filename: Optional[str] = None, recipients_override: Optional[List[str]] = None):
    """
    Send the newsletter individually to each recipient in EMAIL_TO.
    V6 Enhancement: Enforced SMTP_SSL and PGP cryptographic signing.
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

    # Cryptographically sign the content if PGP is configured
    if GPG_KEY_ID:
        logger.info(f"Signing newsletter payload with PGP Key: {GPG_KEY_ID}")
        html_content = sign_payload(html_content)
        text_content = sign_payload(text_content)
        if attachment_content:
            attachment_content = sign_payload(attachment_content)

    context = ssl.create_default_context()

    try:
        # Determine connection method based on port
        if SMTP_PORT == 465:
            # Direct SSL
            server_class = smtplib.SMTP_SSL
            server_kwargs = {"context": context}
        else:
            # Standard SMTP (usually 587) with mandatory STARTTLS
            server_class = smtplib.SMTP
            server_kwargs = {}

        with server_class(SMTP_HOST, SMTP_PORT, **server_kwargs) as server:
            if SMTP_PORT != 465:
                server.starttls(context=context)
            
            server.login(SMTP_USER, SMTP_PASSWORD)

            for recipient in recipients:
                recipient = recipient.strip()
                if not recipient:
                    continue

                logger.info(f"Sending OOB alert to {recipient} (SSL enforced)")

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
                    # Attempt OOB failover for this specific failed recipient
                    if OOB_WEBHOOK_URL:
                        send_webhook_alert(OOB_WEBHOOK_URL, newsletter, error_context=f"Failed for recipient {recipient}: {e}")

                # Small delay to avoid triggering rate limits
                time.sleep(1)

    except Exception as e:
        logger.error(f"SMTP SSL connection error: {e}")
        # Global failover if connection itself failed
        if OOB_WEBHOOK_URL:
            send_webhook_alert(OOB_WEBHOOK_URL, newsletter, error_context=f"Global SMTP connection failure: {e}")
        raise
