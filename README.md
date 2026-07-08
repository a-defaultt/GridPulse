# GridPulse: Out-of-Band (OOB) Threat Intelligence & SecOps Dissemination Engine

![Build Status](https://img.shields.io/badge/build-passing-brightgreen) ![Python](https://img.shields.io/badge/python-3.12-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Docker](https://img.shields.io/badge/docker-ready-blue)

GridPulse is a self-hosted, out-of-band (OOB) threat intelligence aggregation and SecOps dissemination engine designed to solve the "noise" problem in cybersecurity intelligence. It automatically harvests data from community feeds, OSINT feeds, vendor advisories, and Mallory.ai, filters them through a high-fidelity heuristic and AI-powered multi-stage enrichment pipeline, delivers curated daily, weekly, or monthly briefings by email, and keeps a live, deduplicated IOC feed flowing into a shared Google Sheet for analysts to hunt against in real time.

---

## Key Features

- **Multi-Source Aggregation:** Universal parsing across RSS feeds, NVD 2.0 API, CISA Known Exploited Vulnerabilities (KEV), and custom vendor layout scrapers.
- **Parallel Intelligence Streams:** Evaluates incoming telemetry against four independent threat intelligence feeds—AbuseIPDB (verified malicious IPs), Emerging Threats (compromised infrastructure and malware domains), OpenPhish (active phishing URLs), and Mallory.ai (curated observables)—with daily local caching to protect API limits.
- **Mallory.ai Enrichment:** Cross-references extracted and fed IOCs against Mallory.ai's observable graph, attaching confidence, tags, and analyst context where available, capped per run to stay within API budget.
- **Firecrawl Content Enrichment:** Features full-text markdown scraping of top-ranked security briefs to bypass superficial RSS snippets and maximize deep context extraction.
- **Advanced Processing Pipeline:** Employs a robust, two-tier "Heuristic-First, AI-Second" enforcement sequence across deduplication, categorization, and threat scoring.
- **NumPy-Optimized Semantic Deduplication:** Uses local NVIDIA text embedding models to detect and purge near-duplicate entries via vectorized matrix calculations, isolating up to 500 daily candidate records.
- **Neural Passage Reranking:** Merges conventional severity metrics (CVSS, KEV status) with neural ranking evaluations to blend heuristic weights with context relevance on a custom 60/40 scoring split.
- **Adversarial Ingestion Shield:** Implements a strict sanitization layer (`src/utils/sanitizer.py`) that isolates untrusted data in delimited blocks and enforces system-level execution constraints to prevent prompt injection.
- **Cryptographic Payload Integrity:** Natively integrates PGP/GPG signing for every HTML report, providing mathematical proof of origin and protection against transit tampering.
- **OOB Failover Resiliency:** Features an automated pivot mechanism; if primary SMTP SSL dispatch fails or times out, the engine immediately pushes high-severity alerts to secure Webhooks (Slack/Teams/Discord).
- **Live Google Sheet IOC Feed:** Every merged, enriched IOC is appended to a shared Google Sheet via a GCP service account — deduplicated against everything already there — so analysts get a continuously updated, queryable feed instead of a one-off email attachment (which also sidesteps SMTP gateway scanners like Gmail `552 5.7.0` that block raw threat signature lists in transit).
- **Self-Healing Sync Fallback:** If the Sheet is unreachable, IOCs are held in a single local file and automatically merged, deduplicated, and retried on the next run — no data is lost during a Sheets outage, and nothing accumulates once it recovers.
- **Startup Scheduler Guard:** Uses a database-backed 18-hour guard check during container start/restart sequences, checking if a briefing was already dispatched recently to prevent duplicate newsletter delivery.

---

## Architecture

```text
GridPulse/
├── src/
│   ├── aggregator/         # Ingestion Layer (RSS, NVD, CISA, OSINT Feeds, Firecrawl)
│   ├── config/             # High-Availability API & Source Config Synchronization
│   ├── database/           # SQLite Core Management (WAL-Mode Gateway)
│   ├── processor/          # Multi-Stage Filtering, Deduplication, and Reranking Engine
│   ├── generator/          # LLaMA Batch Summarization & Jinja2 Template Compositions
│   ├── delivery/           # SMTP SSL Dispatch, Webhook OOB Failover & Google Sheets IOC Sync
│   ├── utils/              # Sanitization, CSV Serialization and UTC-Strict Timestamps
│   └── main.py             # Global Engine Orchestrator
├── database/               # Relational Schema Tracking & Initialization Blueprints
├── data/                   # Persistent DB Storage & Daily Local JSON Feed Caching
├── logs/                   # Rotating Operational Log Archives
└── templates/              # Jinja2 Production Email Envelopes (HTML & Plain-Text)
```

### Pipeline Dataflow

```mermaid
graph TD
    A[Telemetry Ingestion: RSS / NVD / CISA] --> B(src/aggregator/)
    A2[Parallel IOC Streams: AbuseIPDB / ET / OpenPhish / Mallory.ai] -->|Daily Local JSON Caching| B
    B -->|Top 15 High-Value Articles| C(Firecrawl Markdown Fetcher)
    C -->|Sanitization & Delimiting| D(src/processor/ Intelligence Pipeline)
    D -->|1. Heuristic + NumPy Vector Matrix Dedup| D
    D -->|2. Heuristic + LLM Multi-Label Tagging| D
    D -->|3. CVSS/KEV Score Blended 60/40 with Neural Reranker| D
    D -->|4. Compiled Regex IOC Extraction| D
    D --> E(src/generator/ LLaMA-3.3-Nemotron Batch Summarization)
    E --> J(Mallory.ai Enrichment: confidence / tags / context)
    J -->|Sync, Deduped by type+value| K[(Shared Google Sheet)]
    J -->|On Sync Failure| L[(Local Pending CSV)]
    L -->|Retried & Merged Next Run| K
    E -->|PGP Cryptographic Signing| F(src/delivery/ SMTP SSL Server)
    F -->|Ready-to-Hunt Briefings| G[SecOps Recipients]
    F -->|SMTP Failure Pivot| H[OOB Webhook: Slack / Teams / Discord]
```

### Architecture Philosophy: Framework-Agnostic Processing

To meet tight enterprise security and efficiency footprints, GridPulse completely rejects bloated wrapper frameworks (e.g., LangChain, LlamaIndex) in favor of explicit, deterministic operations.

#### Why Custom & Native?

- **NumPy over Dedicated Vector Databases:** Standard Vector DBs (ChromaDB, Milvus, pgvector) require significant memory overhead and independent system maintenance. Because GridPulse filters highly dense daily pools capped at 500 concurrent candidate articles, performing vector dot-product similarity directly in NumPy matrix arrays delivers microsecond execution times using standard computing hardware.
- **Minimal Dependency Attack Surface:** Interfacing directly with the openai Python client by modifying the endpoint route prevents the framework deprecation loops and black-box runtime behavior typical of enterprise orchestration layers.
- **Database Independence with WAL Mode:** Transitioning the engine onto SQLite 3 running Write-Ahead Logging (WAL) ensures continuous ingestion routines. Aggregation fetchers can seamlessly write intel while generation schedulers simultaneously query existing baselines without locking.

---

## Getting Started

### Prerequisites

- Docker and Docker Compose (v2+)
- NVIDIA Build API Account (One key unlocks all pipeline models)
- SMTP SSL Dispatch Access (Port 465 enforced)
- GPG Keypair (Optional, for payload signing)
- (Optional) AbuseIPDB, Firecrawl, Mallory.ai, and OOB Webhook URLs
- (Optional) GCP Service Account with Sheets/Drive API access, for the live IOC feed sheet

### Installation

1. **Clone the Infrastructure Repo:**
   ```bash
   git clone https://github.com/your-username/GridPulse
   cd GridPulse
   ```

2. **Establish Environment Parameters:**
   ```bash
   cp .env.example .env
   ```

3. **Configure .env:**
   ```env
   # Core AI Model Ingestion
   NVIDIA_SUMMARIZER_KEY=nvapi-your-key
   NVIDIA_EMBEDDING_KEY=nvapi-your-key
   NVIDIA_CATEGORIZER_KEY=nvapi-your-key
   NVIDIA_RERANKER_KEY=nvapi-your-key

   # SMTP SSL Outbound Delivery (Port 465 Mandatory)
   SMTP_HOST=smtp.yourserver.com
   SMTP_PORT=465
   SMTP_USER=dispatch@yourdomain.com
   SMTP_PASSWORD=your-secure-password
   EMAIL_TO=soc-alerts@yourdomain.com

   # OOB Fallback & Security
   OOB_WEBHOOK_URL=https://hooks.slack.com/services/...
   GPG_KEY_ID=your-key-id
   GPG_PASSPHRASE=your-passphrase

   # Mallory.ai IOC Feed + Enrichment (optional)
   MALLORY_API_KEY=your-mallory-key

   # Google Sheets Live IOC Feed (optional — see docs for service account setup)
   GOOGLE_SHEET_ID=your-spreadsheet-id
   GOOGLE_SERVICE_ACCOUNT_FILE=google-service-account.json
   ```

   **Enabling the Google Sheets IOC feed (optional, one-time):**
   1. Create a GCP service account and enable the Sheets + Drive APIs for its project.
   2. Download the service account's JSON key to `google-service-account.json` in the repo root (gitignored).
   3. Create a Google Sheet and share it with the service account's `client_email` as Editor.
   4. Set `GOOGLE_SHEET_ID` to the spreadsheet ID from its URL.

   If skipped, IOCs are held locally in a single pending file (see **Self-Healing Sync Fallback** above) rather than being lost, but you won't get the live shared feed.

4. **Deploy:**
   ```bash
   docker compose up -d --build
   ```
   *Note: Upon successful deployment, GridPulse immediately executes a "Run on Startup" baseline telemetry report. You should receive your first briefing within minutes.*

---

## Tech Stack

- **Runtime Environment:** Python 3.12
- **Data Analytics:** NumPy, PyYAML
- **Database Architecture:** SQLite 3 (WAL Mode Enabled)
- **AI/LLM Architecture (NVIDIA NIM):**
  - **Summarization:** `nvidia/llama-3.3-nemotron-super-49b-v1`
  - **Embeddings:** `nvidia/llama-nemotron-embed-1b-v2`
  - **Categorization:** `meta/llama-3.1-8b-instruct`
  - **Reranking:** `nvidia/llama-nemotron-rerank-1b-v2`
- **Threat Intelligence:** Mallory.ai (`malloryapi` official SDK)
- **IOC Distribution:** Google Sheets API (`gspread`, service-account auth)
- **Security:** GnuPG, SSL/TLS 1.3

---

## Security, Resiliency & Defenses

### High-Availability API Key Rotation
GridPulse tracks all supplied keys inside a distribution pool (`NVIDIA_KEYS`). If an inference task triggers an HTTP 429 Rate Limit, the engine isolates the exception, pivots to the next available key, and transparently attempts to re-execute the batch.

### Adversarial Ingestion Shield (Prompt Injection)
To mitigate LLM-based "jailbreak" or command injection attempts from malicious feed content, GridPulse implements a robust sanitization layer (`src/utils/sanitizer.py`). It enforces strict character-length boundaries and wraps all untrusted telemetry in isolated `[RAW_DATA]` blocks, combined with system-level execution constraints that forbid the model from following instructions contained within the ingested data.

### JSON Recovery Parsers
Because the ultra-fast `meta/llama-3.1-8b-instruct` model can occasionally output trailing text under load, classifications are evaluated using a custom `_safe_parse_json()` sequence. This utilizes `raw_decode` to halt immediately at the primary array boundary, dropping malformed trailing strings.

### IOC Sync Resiliency
The Google Sheet is the sole durable IOC store — there is no more per-run CSV. If a sync attempt fails for any reason (network, auth, missing config), `sync_iocs()` holds the affected IOCs in a single local file instead of dropping them, deduplicated by `(type, value)` so a prolonged outage never reappends the same IOCs run after run. The next successful run merges and uploads the backlog automatically, then deletes the local file.

---

## Troubleshooting

### Persistence & Permissions
If you encounter `sqlite3.OperationalError: unable to open database file`, it is likely due to a host-to-container permission mismatch. 

- **Automatic Fix**: Ensure you use the provided `setup.sh` script, which handles dynamic UID/GID mapping.
- **Manual Fix**: If you ran `docker compose up` as root, you may need to reclaim ownership of the data directories:
  ```bash
  sudo chown -R $USER:$USER data logs
  docker compose up -d --build
  ```

---

## License

Distributed under the MIT License. See LICENSE for further parameters.
