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

# Multi-key rotation support
NVIDIA_KEYS = [
    os.getenv("NVIDIA_PRIMARY_KEY"),
    os.getenv("NVIDIA_FALLBACK_KEY1"),
    os.getenv("NVIDIA_FALLBACK_KEY2"),
    os.getenv("LLM_API_KEY") # Fallback to single key if set
]
NVIDIA_KEYS = [k for k in NVIDIA_KEYS if k] # Filter out empty
NVIDIA_TIMEOUT = int(os.getenv("NVIDIA_TIMEOUT_SECONDS", 120))
