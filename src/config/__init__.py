# src/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "GridPulse.db"))
SOURCES_YAML = os.getenv("SOURCES_YAML", str(BASE_DIR / "sources.yaml"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEZONE = os.getenv("TIMEZONE", "Africa/Tunis")

# Email Settings
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO", "").split(",")

# PGP Settings
GPG_HOME = os.getenv("GPG_HOME", str(Path.home() / ".gnupg"))
GPG_PASSPHRASE = os.getenv("GPG_PASSPHRASE")
GPG_KEY_ID = os.getenv("GPG_KEY_ID")

# OOB Fallback
OOB_WEBHOOK_URL = os.getenv("OOB_WEBHOOK_URL")

# API Keys
NVD_API_KEY = os.getenv("NVD_API_KEY")
ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
MALLORY_API_KEY = os.getenv("MALLORY_API_KEY")
MALLORY_ENRICHMENT_LIMIT = int(os.getenv("MALLORY_ENRICHMENT_LIMIT", 50))

# Google Sheets IOC Sync (service account, headless Docker deployment)
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(BASE_DIR / "google-service-account.json"))
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_WORKSHEET_NAME = os.getenv("GOOGLE_SHEET_WORKSHEET_NAME", "IOCs")
# Human-facing link to the shared IOC sheet, used in newsletter emails
GOOGLE_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit" if GOOGLE_SHEET_ID else ""
GOOGLE_SHEETS_SYNC_ENABLED = os.getenv("GOOGLE_SHEETS_SYNC_ENABLED", "true").lower() in ("true", "1", "yes")

# LLM Settings
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "meta/llama3-70b-instruct")

# Per-feature NVIDIA API keys (named by purpose)
NVIDIA_SUMMARIZER_KEY = os.getenv("NVIDIA_SUMMARIZER_KEY")
NVIDIA_EMBEDDING_KEY = os.getenv("NVIDIA_EMBEDDING_KEY")
NVIDIA_CATEGORIZER_KEY = os.getenv("NVIDIA_CATEGORIZER_KEY")
NVIDIA_RERANKER_KEY = os.getenv("NVIDIA_RERANKER_KEY")

# Rotation pool: all unique keys for rate-limit fallback (order preserved)
NVIDIA_KEYS = list(dict.fromkeys(
    k for k in [
        NVIDIA_SUMMARIZER_KEY,
        NVIDIA_EMBEDDING_KEY,
        NVIDIA_CATEGORIZER_KEY,
        NVIDIA_RERANKER_KEY,
        os.getenv("LLM_API_KEY"),  # Legacy fallback
    ]
    if k
))
NVIDIA_TIMEOUT = int(os.getenv("NVIDIA_TIMEOUT_SECONDS", 120))

# V5.2 AI Enhancement Models
AI_ENHANCEMENTS = os.getenv("AI_ENHANCEMENTS", "true").lower() in ("true", "1", "yes")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nvidia/llama-nemotron-embed-1b-v2")
CATEGORIZER_MODEL = os.getenv("CATEGORIZER_MODEL", "meta/llama-3.1-8b-instruct")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "nvidia/llama-nemotron-rerank-1b-v2")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
