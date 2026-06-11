import pytest
from src.delivery import email_sender, webhook_sender

def test_send_webhook_alert_success(monkeypatch):
    class FakeResponse:
        status_code = 200
        def raise_for_status(self):
            pass

    def mock_post(url, json, timeout):
        assert "OOB Failover Alert" in json["text"]
        return FakeResponse()

    monkeypatch.setattr(webhook_sender.requests, "post", mock_post)
    
    newsletter = {"subject": "Test", "content_text": "Body"}
    webhook_sender.send_webhook_alert("https://test.com", newsletter, "Test Error")

def test_email_sender_failover(monkeypatch):
    # Mock SMTP to fail
    class FakeSMTPFail:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def login(self, *args): raise Exception("SMTP Auth Failed")

    monkeypatch.setattr(email_sender.smtplib, "SMTP_SSL", FakeSMTPFail)
    
    # Track webhook calls
    webhook_calls = []
    def mock_send_webhook_alert(url, newsletter, error_context):
        webhook_calls.append(error_context)

    monkeypatch.setattr(email_sender, "send_webhook_alert", mock_send_webhook_alert)
    monkeypatch.setattr(email_sender, "OOB_WEBHOOK_URL", "https://oob.webhook")
    monkeypatch.setattr(email_sender, "SMTP_USER", "user")
    monkeypatch.setattr(email_sender, "SMTP_PASSWORD", "pass")
    monkeypatch.setattr(email_sender, "EMAIL_TO", ["test@test.com"])

    with pytest.raises(Exception):
        email_sender.send_individual_emails({"subject": "X", "content_text": "Y"})

    assert len(webhook_calls) > 0
    assert "Global SMTP connection failure" in webhook_calls[0]
