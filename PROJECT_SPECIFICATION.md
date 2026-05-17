# GridPulse V5.5: Production-Ready Cyber Intelligence Aggregator

## 1. Executive Summary
GridPulse is a self-hosted platform designed to solve the "noise" problem in cybersecurity intelligence. Built on **Python 3.12**, it aggregates data from dozens of sources, uses heuristic and AI-powered filters to deduplicate and rank information, and delivers high-signal summaries to security professionals via automated newsletters.

## 2. File System Hierarchy
```text
GridPulse/
├── data/                   # Persistent SQLite database storage
├── database/
│   └── schema.sql          # Final V5 schema with migration tracking
├── logs/                   # Rotating application logs (gridpulse.log)
├── src/                    # Primary Source Code
│   ├── aggregator/         # Data Ingestion Layer
│   │   ├── rss_fetcher.py      # Universal RSS parser with score filtering
│   │   ├── nvd_client.py       # NVD 2.0 API integration
│   │   ├── cisa_kev.py         # CISA Known Exploited Vulns integration
│   │   ├── threatfox_client.py  # abuse.ch ThreatFox IOC feed (V5.5)
│   │   ├── otx_client.py        # AlienVault OTX IOC feed (V5.5)
│   │   ├── firecrawl_client.py  # Surgical full-content fetcher (V5.5)
│   │   └── vendor_advisories.py # Legacy scrapers (e.g., Adobe fallback)
│   ├── config/             # Configuration & Source Management
│   │   ├── __init__.py         # Environment loading & Per-feature key setup
│   │   └── source_manager.py   # Hybrid YAML/DB source synchronization
│   ├── database/           # Database Handlers
│   │   └── db_handler.py       # Connection management (WAL mode enabled)
│   ├── delivery/           # Newsletter Distribution
│   │   ├── email_sender.py     # Looped SMTP delivery with attachment support
│   │   └── scheduler.py        # Internal Python-based job scheduler
│   ├── generator/          # Content Composition
│   │   ├── __init__.py         # Unified generator orchestrator
│   │   ├── content_selector.py # Scoring-based article selection
│   │   ├── daily_generator.py  # Daily Jinja2 rendering logic
│   │   ├── weekly_generator.py # Weekly Jinja2 rendering logic
│   │   ├── monthly_generator.py# Monthly Jinja2 rendering logic
│   │   └── summary_generator.py # Batch LLM summarization with key rotation
│   ├── processor/          # Multi-Stage Intelligence Pipeline
│   │   ├── categorizer.py      # Heuristic keyword-based tagging
│   │   ├── ai_categorizer.py   # LLM-powered multi-label classification
│   │   ├── deduplicator.py     # Exact URL/Title deduplication
│   │   ├── ai_deduplicator.py  # Semantic embedding-based dedup (NumPy optimized)
│   │   ├── ranker.py           # Heuristic CVSS/Source relevance scoring
│   │   ├── ai_ranker.py        # Neural passage reranking & score blending
│   │   ├── ioc_extractor.py    # IOC extraction with full_content support (V5.5)
│   │   └── freshness.py        # 7-day rolling window temporal filter
│   ├── utils/              # Shared Utilities
│   │   ├── csv_utils.py        # IOC CSV generation helpers
│   │   └── datetime_utils.py   # UTC-aware ISO 8601 serialization
│   └── main.py             # Pipeline Orchestrator (Fetch -> Process -> Gen -> Deliver)
├── systemd/                # Linux systemd unit templates
├── templates/              # Jinja2 HTML/Text templates
├── tests/                  # Pytest suite (Unit & Connectivity)
├── Dockerfile              # Production container definition
├── docker-compose.yml      # Orchestration (Volumes, Env, Networking)
├── docker-entrypoint.sh    # Container startup and initialization script
├── requirements.txt        # Python dependency manifest (NumPy, OpenAI, etc.)
├── run.py                  # CLI Entry point with log rotation setup
└── sources.yaml            # Version-controlled ingestion definitions
```

## 3. The Multi-Stage Pipeline (Fetch-Process-Gen-Deliver)

### 3.1 Aggregation
The system polls `sources.yaml`. API sources (NVD/CISA) are handled via dedicated clients. RSS sources are handled by a universal fetcher.
*   **Adobe Logic:** Automatically detects if a vendor uses RSS or requires legacy scraping.
*   **Score Filtering:** Ingests `min_score` for community feeds (e.g., Hacker News) to ensure quality.
*   **NOT IMPLEMENTED (TODO):** AlienVault OTX integration was previously a placeholder — now implemented in V5.5 (`otx_client.py`).

### 3.1b Parallel IOC Feeds (V5.5)
In addition to RSS/NVD/CISA article sources, the pipeline now queries five parallel IOC intelligence feeds that run independently from `sources.yaml`:
*   **AbuseIPDB (`abuseipdb_client.py`):** Verified malicious IP blacklist. Requires `ABUSEIPDB_API_KEY`. Filtered by confidence ≥ 90 and capped at 500 IPs.
*   **Emerging Threats (`emerging_threats_client.py`):** Proofpoint's free compromised IP and botnet C2 domain blocklists. No authentication required. Capped at 1000 entries per type.
*   **OpenPhish (`openphish_client.py`):** Community feed of verified active phishing URLs. No authentication required. Automatically extracts domains from URLs for broader coverage.
*   **ThreatFox (`threatfox_client.py`):** abuse.ch community-curated IOCs. Requires `THREATFOX_API_KEY` (due to their 2024 policy update). Filtered by confidence ≥ 75. Includes smart 401 fail-fast handling.
*   **AlienVault OTX (`otx_client.py`):** Subscribed pulse indicators. Requires `OTX_API_KEY`. Paginated with a safety cap of 5 pages (100 pulses max). Includes a fast metadata-first fetch strategy and circuit breaker to prevent the pipeline from hanging on AlienVault outages.

### 3.1c Firecrawl Content Enrichment (V5.5)
After ranking, the top 15 highest-scoring articles are sent to the **Firecrawl API** to fetch their full markdown content. This replaces the truncated RSS `summary` with complete article text, dramatically improving IOC extraction quality.
*   **Budget Guard:** Hard-capped at 15 articles/run (≤ 450 credits/month on free tier).
*   **402 Safety Net:** If a `402 Payment Required` response is received (credits exhausted), the crawl halts immediately and remaining articles keep their original summaries.
*   **Requires:** `FIRECRAWL_API_KEY` in `.env` (optional — pipeline continues without it).

### 3.2 Intelligence Processing ("The Enrichment Pattern")
GridPulse follows a strict **"Heuristic First, AI Second"** pattern. AI never replaces the baseline; it enriches it.
1.  **Deduplication:**
    *   *Heuristic:* Removes identical URLs or normalized titles.
    *   *AI (V5.4):* Uses NVIDIA embeddings to remove semantically similar articles. Optimized with **NumPy** for vector matrix operations and capped at the top **500 articles** to ensure high-performance execution.
2.  **Categorization:**
    *   *Heuristic:* Fast regex-based tagging (vulnerability, malware).
    *   *AI:* Uses LLM to identify context (state-sponsored, zero-day) that keywords miss.
3.  **Ranking:**
    *   *Heuristic:* Scores based on CVSS, KEV status, and Source Priority.
    *   *AI:* Uses a Neural Reranker to score relevance against a "SOC-focused" query, blending with the heuristic score (40/60 split).
4.  **IOC Extraction (V5.5):**
    *   Automatically extracts **IP addresses, Domains, and File Hashes (MD5, SHA1, SHA256)** using optimized compiled regex patterns.
    *   Excludes RFC-1918 private IP ranges and common noise domains.
    *   Uses `full_content` (Firecrawl) when available, falls back to `summary`. Tags the `extraction_source` field so CSV consumers can weight quality tiers.

### 3.3 Generation & Summarization
*   **Batching:** Sends articles in batches of 10-15 to the LLM to minimize latency and bypass rate limits.
*   **Summarization:** LLM generates 2-3 sentence summaries focusing on "Impact" and "Action Required."
*   **Dynamic Metadata:** Templates display `published_date` for each article and utilize dynamic `edition_title` headers (Daily/Weekly/Monthly).

### 3.4 NVIDIA NIM Model Assignments & Selection Rationale
The pipeline uses specific NVIDIA NIM models for each task, assigned via dedicated API keys to maximize the free tier rate limits.

#### 1. Summarization (`NVIDIA_SUMMARIZER_KEY`)
*   **Endpoint:** `/v1/chat/completions`
*   **🥇 Best (Default):** `nvidia/llama-3.3-nemotron-super-49b-v1` (NVIDIA's flagship; best JSON adherence and cybersecurity reasoning).

#### 2. Semantic Deduplication (`NVIDIA_EMBEDDING_KEY`)
*   **Endpoint:** `/v1/embeddings`
*   **🥇 Best (Default):** `nvidia/llama-nemotron-embed-1b-v2` (Multilingual, long-doc, optimized for passage similarity).

#### 3. AI Categorization (`NVIDIA_CATEGORIZER_KEY`)
*   **Endpoint:** `/v1/chat/completions`
*   **🥇 Best (Default):** `meta/llama-3.1-8b-instruct` (Fast, cheap, highly deterministic for multi-label classification).

#### 4. Neural Reranking (`NVIDIA_RERANKER_KEY`)
*   **Endpoint:** `/retrieval/nvidia/{model}/reranking` (Custom model-specific path)
*   **🥇 Best (Default):** `nvidia/llama-nemotron-rerank-1b-v2` (GPU-accelerated, purpose-built for passage reranking).

## 4. Database Architecture
*   **Engine:** SQLite 3.
*   **Concurrency:** **WAL (Write-Ahead Logging)** mode is enabled globally. This allows the aggregator to write new findings while the generator reads data for a newsletter simultaneously without `database is locked` errors.
*   **Consistency:** All dates are stored as **ISO 8601 UTC strings**. The `datetime_utils.py` module is the strict gateway for all DB date operations.

## 5. Advanced Configuration & Resiliency

### 5.1 Per-Feature API Key Management
To maximize the NVIDIA NIM free tier, the system maps keys by task:
*   `NVIDIA_SUMMARIZER_KEY`
*   `NVIDIA_EMBEDDING_KEY`
*   `NVIDIA_CATEGORIZER_KEY`
*   `NVIDIA_RERANKER_KEY`

**API Key Rotation (Rate Limit Evasion):**
In `src/config/__init__.py`, all provided keys are aggregated into a deduplicated pool (`NVIDIA_KEYS`). If an AI module catches an `HTTP 429 Rate Limit` error, it automatically catches the exception, rotates to the next key in the pool, and retries the batch.

### 5.2 Standardized AI Client
The project exclusively uses the official `openai` Python package for all LLM Chat and Embedding calls by swapping the `base_url` to `https://integrate.api.nvidia.com/v1`. The only exception is the Neural Reranker, which uses `requests` because the reranking endpoint is a custom path and not OpenAI-compatible.

### 5.3 Delivery & Attachments (V5.5)
*   **Individual SMTP:** Emails are sent one-by-one to the `EMAIL_TO` list to ensure recipient privacy.
*   **IOC CSV Attachments:** Every newsletter includes a generated `.csv` attachment containing IOCs from **six merged streams**: AbuseIPDB, Emerging Threats, OpenPhish, ThreatFox, AlienVault OTX, and article-extracted IOCs. The `source` column distinguishes origin so analysts can filter by tier.

### 5.4 External API Reference
All external APIs used by the pipeline and their authentication:

| API | Client File | Key Required | Free Tier Limits |
|---|---|---|---|
| **NVIDIA NIM** (Chat/Embed/Rerank) | `summary_generator.py`, `ai_*.py` | `NVIDIA_*_KEY` | Per-model rate limits |
| **NVD 2.0** | `nvd_client.py` | `NVD_API_KEY` | 5 req/30s without key, 50 with |
| **CISA KEV** | `cisa_kev.py` | None | Unrestricted |
| **AbuseIPDB** | `abuseipdb_client.py` | `ABUSEIPDB_API_KEY` | 1,000 req/day |
| **Emerging Threats** | `emerging_threats_client.py` | None | Unrestricted |
| **OpenPhish** | `openphish_client.py` | None | Unrestricted |
| **ThreatFox** (abuse.ch) | `threatfox_client.py` | `THREATFOX_API_KEY` | Unrestricted |
| **AlienVault OTX** | `otx_client.py` | `OTX_API_KEY` | Rate-limited per endpoint |
| **Firecrawl** | `firecrawl_client.py` | `FIRECRAWL_API_KEY` | 1,000 credits/month |

## 6. Operational Guidelines

### Manual Execution
```bash
./run.py --edition daily --dry-run   # Test without sending
./run.py --edition weekly            # Full production run
```

### Docker Deployment
The container runs an internal `scheduler.py` loop. It persists the database to the `data/` volume and logs to the `logs/` volume.
```bash
docker-compose up -d --build
```

## 7. Development Standards
1.  **UTC Everywhere:** Never use `datetime.now()` without `timezone.utc`.
2.  **Graceful Fallback:** AI modules must catch all exceptions and return the original article list so the pipeline continues.
3.  **Atomic Edits:** ALWAYS update `schema.sql` and `PROJECT_SPECIFICATION.md` when changing core architecture or adding major features.
