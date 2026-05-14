# GridPulse V5

GridPulse is a self-hosted cybersecurity newsletter aggregator. It fetches vulnerability data, security news, and vendor advisories, processes them with LLM-powered summarization, and delivers a curated daily/weekly/monthly briefing.

## Features

- **Multi-source Aggregation:** RSS feeds, NVD API, CISA KEV, and custom vendor scrapers (e.g., Adobe).
- **Production-Ready Core:** SQLite with WAL mode for concurrency, rotating logs, and robust error handling.
- **LLM Summarization:** Batch prompting via standard OpenAI client (works with NVIDIA NIM, Groq, etc.).
- **Secure Delivery:** Individual email dispatch to protect recipient privacy and prevent spam flags.
- **Automated Scheduling:** Systemd timer templates included.

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd GridPulse
   ```

2. **Set up virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials and API keys
   ```

4. **Initialize Sources:**
   Edit `sources.yaml` to add/remove your preferred security feeds.

## Usage

### Docker (Recommended)
1. **Configure:**
   ```bash
   cp .env.example .env
   # Edit .env
   ```
2. **Build and Run:**
   ```bash
   docker-compose up -d --build
   ```
This will start the internal scheduler which runs the pipeline according to the predefined schedule.

### Run manually (CLI)
```bash
source venv/bin/activate
./run.py --edition daily --dry-run  # Dry run (logs content)
./run.py --edition daily            # Generate and send
```

### Scheduled Runs (Systemd)
Copy files from `systemd/` to `/etc/systemd/system/`, update paths, and enable:
```bash
sudo systemctl enable --now GridPulse-daily.timer
```

## Testing
```bash
source venv/bin/activate
pytest tests/
```
