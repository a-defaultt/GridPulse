"""
Google Sheets Sync — Best-effort append of new IOCs to a shared Google Sheet
via a GCP service account (headless-safe, no interactive OAuth).

Never raises: any failure is logged and the pipeline continues, same
"last resort, swallow everything" style as webhook_sender.py.

Dedup: only rows whose (type, value) are not already present in the sheet
(read from columns A+B only, via a single batched range read) are appended,
since this is a long-lived shared file, not a per-run artifact like the CSV.
"""
import logging

import gspread

from src.config import (
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_SHEET_ID,
    GOOGLE_SHEET_WORKSHEET_NAME,
    GOOGLE_SHEETS_SYNC_ENABLED,
)
from src.utils.datetime_utils import dt_to_str, utc_now

logger = logging.getLogger(__name__)

SHEET_HEADER = [
    "type", "value", "source", "confidence", "malware_family", "threat_type",
    "mallory_tags", "mallory_context", "source_article", "source_url", "added_utc",
]


def push_iocs_to_sheet(iocs: list[dict]) -> None:
    """
    Appends IOCs not already present in the configured sheet.
    Best-effort: returns silently on missing config or any exception.
    """
    if not iocs:
        return
    if not GOOGLE_SHEETS_SYNC_ENABLED:
        logger.info("[GoogleSheets] Sync disabled via GOOGLE_SHEETS_SYNC_ENABLED. Skipping.")
        return
    if not GOOGLE_SHEET_ID or not GOOGLE_SERVICE_ACCOUNT_FILE:
        logger.warning("[GoogleSheets] GOOGLE_SHEET_ID or GOOGLE_SERVICE_ACCOUNT_FILE not set. Skipping.")
        return

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
            return

        ws.append_rows(rows, value_input_option="RAW")
        logger.info(
            f"[GoogleSheets] Appended {len(rows)} new IOC rows "
            f"(skipped {len(iocs) - len(rows)} already-present/duplicate)."
        )
    except Exception as e:
        logger.error(f"[GoogleSheets] Sync failed: {e}. Continuing without sheet update.")


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
