# GridPulse V5.6

GridPulse is a self-hosted cybersecurity newsletter aggregator. It fetches vulnerability data, security news, and vendor advisories, processes them through an AI-powered intelligence pipeline, extracts Indicators of Compromise (IOCs), and delivers curated daily/weekly/monthly briefings with actionable CSV attachments.

## Features

- **Multi-source Aggregation:** RSS feeds, NVD API, CISA KEV, and custom vendor scrapers (e.g., Adobe).
- **Parallel Intelligence Feeds (V5.6):** Three high-fidelity IOC streams run alongside the article pipeline — AbuseIPDB (verified malicious IPs), Emerging Threats (compromised IPs + malware domains), and OpenPhish (active phishing URLs + domains). All three results are **cached daily** so running multiple editions in the same day costs only one network request each.
- **Firecrawl Content Enrichment (V5.5):** Surgical markdown scraping of top-ranked articles for deep context.
- **Production-Ready Core:** SQLite with WAL mode for concurrency, rotating logs, and robust error handling.
- **AI-Powered Pipeline (V5.5):**
  - **LLM Summarization:** Batch prompting via NVIDIA NIM (`nvidia/llama-3.3-nemotron-super-49b-v1`).
  - **Semantic Deduplication (NumPy Optimized):** Embedding-based near-duplicate detection (`nvidia/llama-nemotron-embed-1b-v2`).
  - **AI Categorization:** LLM multi-label classification enriching keyword-based tagging (`meta/llama-3.1-8b-instruct`).
  - **Neural Reranking:** Passage reranker blended with heuristic scoring (`nvidia/llama-nemotron-rerank-1b-v2`).
  - **Deep IOC Extraction:** Regex-based extraction running on Firecrawl's full markdown content instead of just RSS summaries.
- **Dynamic Content:** Generates specific Daily, Weekly, or Monthly editions automatically.
- **Secure Delivery:** Individual email dispatch to protect recipient privacy, including an auto-generated CSV attachment for threat hunting.
- **Automated Scheduling:** Systemd timer templates and Docker-based scheduler included.

## Installation

### One-Command Setup (Linux)
The fastest way to deploy on a new server. This script installs Docker, Docker Compose, and starts the project automatically:
```bash
chmod +x setup.sh && ./setup.sh
```

### Manual Installation
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

4. **Get NVIDIA API Keys:**
   - Sign up at [build.nvidia.com](https://build.nvidia.com)
   - Generate an API key (one key works for all models)
   - Fill in the `NVIDIA_*_KEY` fields in `.env`

5. **Initialize Sources:**
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
./run.py --edition daily --dry-run  # Dry run (logs content without sending email)
./run.py --edition daily            # Generate and send daily edition
./run.py --edition weekly           # Generate and send weekly edition
./run.py --edition monthly          # Generate and send monthly edition
```

### Scheduled Runs (Systemd)
Copy files from `systemd/` to `/etc/systemd/system/`, update paths, and enable:
```bash
sudo systemctl enable --now GridPulse-daily.timer
```

## Configuration

### NVIDIA API Keys

Each AI feature has its own dedicated key for independent rate limits:

| Key | Purpose | Model |
|-----|---------|-------|
| `NVIDIA_SUMMARIZER_KEY` | LLM batch summarization | `nvidia/llama-3.3-nemotron-super-49b-v1` |
| `NVIDIA_EMBEDDING_KEY` | Semantic deduplication | `nvidia/llama-nemotron-embed-1b-v2` |
| `NVIDIA_CATEGORIZER_KEY` | AI article categorization | `meta/llama-3.1-8b-instruct` |
| `NVIDIA_RERANKER_KEY` | Neural reranking | `nvidia/llama-nemotron-rerank-1b-v2` |

> **Tip:** One API key from build.nvidia.com works for all models. Use separate keys only if you need independent rate limit pools.

### IOC Feed Keys

| Key | Feed | Notes |
|-----|------|-------|
| `ABUSEIPDB_API_KEY` | AbuseIPDB blacklist | Optional. Free tier: 1,000 req/day. Results cached daily to `data/abuseipdb_cache.json`. |
| *(none)* | Emerging Threats | Public feed — no key needed. Cached to `data/emerging_threats_cache.json`. |
| *(none)* | OpenPhish | Public feed — no key needed. Cached to `data/openphish_cache.json`. |

> **Tip:** Because all three feeds cache their results for the calendar day, you can safely run daily + weekly + monthly editions without hitting rate limits.

### Disabling AI Enhancements

Set `AI_ENHANCEMENTS=false` in `.env` to fall back to traditional processing only (keyword categorization, exact dedup, heuristic ranking). LLM summarization remains active independently.

## Testing
```bash
source venv/bin/activate
pytest tests/
```
