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
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO", "").split(",")

# API Keys
NVD_API_KEY = os.getenv("NVD_API_KEY")

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
