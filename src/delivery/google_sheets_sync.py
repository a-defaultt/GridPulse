"""
Google Sheets Sync — Best-effort append of new IOCs to a shared Google Sheet
via a GCP service account (headless-safe, no interactive OAuth).

Never raises: any failure is logged and the pipeline continues, same
"last resort, swallow everything" style as webhook_sender.py.

Dedup: only rows whose (type, value) are not already present in the sheet
(read from columns A+B only, via a single batched range read) are appended,
since this is a long-lived shared file, not a per-run artifact like the CSV.

Local fallback: the Sheet is now the only durable IOC store — there is no
more per-run CSV. If a sync attempt fails for any reason (network, auth,
missing config, or GOOGLE_SHEETS_SYNC_ENABLED=false), sync_iocs() writes the
IOCs to a single consolidated local file (PENDING_FILE) instead. The next
run merges that backlog with its own new IOCs, deduping by (type, value)
before retrying — so a prolonged outage doesn't reappend the same IOCs to
the pending file run after run, and once the Sheet is reachable again the
backlog uploads and the local file is deleted.
"""
import csv
import logging
import os

import gspread

from src.config import (
    DATA_DIR,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_SHEET_ID,
    GOOGLE_SHEET_WORKSHEET_NAME,
    GOOGLE_SHEETS_SYNC_ENABLED,
)
from src.utils.csv_utils import generate_ioc_csv
from src.utils.datetime_utils import dt_to_str, utc_now

logger = logging.getLogger(__name__)

SHEET_HEADER = [
    "type", "value", "source", "confidence", "malware_family", "threat_type",
    "mallory_tags", "mallory_context", "source_article", "source_url", "added_utc",
]

PENDING_FILE = DATA_DIR / "gridpulse_iocs_pending_upload.csv"


def sync_iocs(iocs: list[dict]) -> bool:
    """
    Syncs `iocs` to the shared Google Sheet, merged with any IOCs left over
    from a previously failed sync. On success, clears the local pending
    file. On failure, persists the (deduped) combined set to PENDING_FILE
    for the next run to retry. Returns True iff the Sheet is up to date.
    """
    pending = _load_pending()
    combined = _dedupe_by_type_value(pending + iocs)
    if not combined:
        return True

    if push_iocs_to_sheet(combined):
        _clear_pending()
        return True

    _save_pending(combined)
    logger.warning(
        f"[GoogleSheets] Sync unavailable — {len(combined)} IOCs held locally "
        f"in {PENDING_FILE} for retry on the next run."
    )
    return False


def push_iocs_to_sheet(iocs: list[dict]) -> bool:
    """
    Appends IOCs not already present in the configured sheet.
    Best-effort: returns False (never raises) on missing config or any
    exception; True on success or if there was nothing to push.
    """
    if not iocs:
        return True
    if not GOOGLE_SHEETS_SYNC_ENABLED:
        logger.info("[GoogleSheets] Sync disabled via GOOGLE_SHEETS_SYNC_ENABLED. Skipping.")
        return False
    if not GOOGLE_SHEET_ID or not GOOGLE_SERVICE_ACCOUNT_FILE:
        logger.warning("[GoogleSheets] GOOGLE_SHEET_ID or GOOGLE_SERVICE_ACCOUNT_FILE not set. Skipping.")
        return False

    try:
        gc = gspread.service_account(filename=GOOGLE_SERVICE_ACCOUNT_FILE)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        try:
            ws = sh.worksheet(GOOGLE_SHEET_WORKSHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=GOOGLE_SHEET_WORKSHEET_NAME, rows=1000, cols=len(SHEET_HEADER))
            ws.append_row(SHEET_HEADER, value_input_option="RAW")

        existing = _existing_keys(ws)
        rows = _build_new_rows(iocs, existing)

        if not rows:
            logger.info("[GoogleSheets] No new IOCs to append (all already present).")
            return True

        ws.append_rows(rows, value_input_option="RAW")
        logger.info(
            f"[GoogleSheets] Appended {len(rows)} new IOC rows "
            f"(skipped {len(iocs) - len(rows)} already-present/duplicate)."
        )
        return True
    except Exception as e:
        logger.error(f"[GoogleSheets] Sync failed: {e}. Continuing without sheet update.")
        return False


def _dedupe_by_type_value(iocs: list[dict]) -> list[dict]:
    """Keeps the first occurrence of each (type, value) pair, preserving order."""
    seen = set()
    deduped = []
    for ioc in iocs:
        typ = ioc.get("type") or ioc.get("ioc_type", "")
        val = ioc.get("value") or ioc.get("ioc_value", "")
        key = (typ, val)
        if not typ or not val or key in seen:
            continue
        seen.add(key)
        deduped.append(ioc)
    return deduped


def _load_pending() -> list[dict]:
    if not os.path.exists(PENDING_FILE):
        return []
    try:
        with open(PENDING_FILE, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        logger.warning(f"[GoogleSheets] Failed to read pending file ({e}). Starting fresh.")
        return []


def _save_pending(iocs: list[dict]) -> None:
    content = generate_ioc_csv(iocs)
    os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def _clear_pending() -> None:
    if os.path.exists(PENDING_FILE):
        os.remove(PENDING_FILE)


def _existing_keys(ws) -> set[tuple[str, str]]:
    """Single batched read of columns A+B (skips header row)."""
    values = ws.get("A2:B")
    return {(row[0], row[1]) for row in values if len(row) >= 2}


def _build_new_rows(iocs: list[dict], existing: set[tuple[str, str]]) -> list[list]:
    added_at = dt_to_str(utc_now())
    rows = []
    seen_this_run = set(existing)
    for ioc in iocs:
        typ = ioc.get("type") or ioc.get("ioc_type", "")
        val = ioc.get("value") or ioc.get("ioc_value", "")
        key = (typ, val)
        if not typ or not val or key in seen_this_run:
            continue
        seen_this_run.add(key)
        rows.append([
            typ, val,
            ioc.get("source", ""),
            ioc.get("confidence", ""),
            ioc.get("malware_family", ""),
            ioc.get("threat_type", ""),
            ioc.get("mallory_tags", ""),
            ioc.get("mallory_context", ""),
            ioc.get("article_title", ""),
            ioc.get("linked_article", ""),
            added_at,
        ])
    return rows
