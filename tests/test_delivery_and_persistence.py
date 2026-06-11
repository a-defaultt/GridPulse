import sqlite3

from src.database import db_handler
from src.delivery import email_sender


def test_upsert_articles_and_record_newsletter(db_path, monkeypatch):
    monkeypatch.setattr(db_handler, "DATABASE_PATH", db_path)

    articles = [
        {
            "title": "Critical CVE",
            "url": "https://example.com/cve",
            "source": "Unit Test",
            "source_type": "rss",
            "published_date": "2026-06-04T10:00:00Z",
            "fetched_date": "2026-06-04T10:05:00Z",
            "summary": "A critical issue",
            "topics": "vulnerability",
            "cve_id": "CVE-2026-12345",
            "relevance_score": 9.5,
            "is_featured": 1,
        }
    ]

    persisted = db_handler.upsert_articles(articles)
    assert persisted[0]["id"]

    newsletter = {
        "subject": "GridPulse Test",
        "content_html": "<p>test</p>",
        "content_text": "test",
        "article_count": 1,
        "edition_number": 1,
    }
    newsletter_id = db_handler.record_newsletter(newsletter, "daily", persisted)

    with sqlite3.connect(db_path) as conn:
        article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        link = conn.execute("""
            SELECT newsletter_id, article_id, edition_type, position, is_featured
            FROM newsletter_articles
        """).fetchone()

    assert article_count == 1
    assert link == (newsletter_id, persisted[0]["id"], "daily", 1, 1)


class FakeSMTP:
    sent_to = []

    def __init__(self, host, port, context=None):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, user, password):
        pass

    def send_message(self, msg):
        self.sent_to.append(msg["To"])


def test_send_individual_emails_uses_recipient_override(monkeypatch):
    FakeSMTP.sent_to = []
    monkeypatch.setattr(email_sender, "SMTP_USER", "user")
    monkeypatch.setattr(email_sender, "SMTP_PASSWORD", "password")
    monkeypatch.setattr(email_sender, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_sender, "SMTP_PORT", 465)
    monkeypatch.setattr(email_sender, "EMAIL_FROM", "from@example.com")
    monkeypatch.setattr(email_sender, "EMAIL_TO", ["prod@example.com"])
    monkeypatch.setattr(email_sender, "GPG_KEY_ID", None)
    monkeypatch.setattr(email_sender.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(email_sender.time, "sleep", lambda _: None)

    email_sender.send_individual_emails(
        {"subject": "Test", "content_html": "<p>x</p>", "content_text": "x"},
        recipients_override=["ahmed.slaimia@manucurist.com"],
    )

    assert FakeSMTP.sent_to == ["ahmed.slaimia@manucurist.com"]
