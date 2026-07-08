import gspread
import pytest

from src.delivery import google_sheets_sync as gss


class FakeWorksheet:
    def __init__(self, existing_rows=None):
        self._existing_rows = existing_rows or []
        self.appended_rows = None
        self.appended_header = None

    def get(self, range_name):
        return self._existing_rows

    def append_rows(self, rows, value_input_option="RAW"):
        self.appended_rows = rows

    def append_row(self, row, value_input_option="RAW"):
        self.appended_header = row


class FakeSpreadsheet:
    def __init__(self, worksheet=None, missing=False):
        self._worksheet = worksheet
        self._missing = missing
        self.added_worksheet = None

    def worksheet(self, title):
        if self._missing:
            raise gspread.WorksheetNotFound(title)
        return self._worksheet

    def add_worksheet(self, title, rows, cols):
        self.added_worksheet = FakeWorksheet()
        self._worksheet = self.added_worksheet
        self._missing = False
        return self.added_worksheet


def _configure(monkeypatch, sheet_id="sheet123", cred_file="creds.json", enabled=True):
    monkeypatch.setattr(gss, "GOOGLE_SHEET_ID", sheet_id)
    monkeypatch.setattr(gss, "GOOGLE_SERVICE_ACCOUNT_FILE", cred_file)
    monkeypatch.setattr(gss, "GOOGLE_SHEETS_SYNC_ENABLED", enabled)


def test_push_iocs_no_config(monkeypatch):
    _configure(monkeypatch, sheet_id=None)

    def exploding_service_account(filename):
        raise AssertionError("gspread should not be touched when config is missing")

    monkeypatch.setattr(gss.gspread, "service_account", exploding_service_account)
    gss.push_iocs_to_sheet([{"type": "ip", "value": "1.2.3.4"}])


def test_push_iocs_sync_disabled(monkeypatch):
    _configure(monkeypatch, enabled=False)

    def exploding_service_account(filename):
        raise AssertionError("gspread should not be touched when sync is disabled")

    monkeypatch.setattr(gss.gspread, "service_account", exploding_service_account)
    gss.push_iocs_to_sheet([{"type": "ip", "value": "1.2.3.4"}])


def test_push_iocs_dedups_against_existing_rows(monkeypatch):
    _configure(monkeypatch)
    ws = FakeWorksheet(existing_rows=[["ip", "1.2.3.4"]])
    sh = FakeSpreadsheet(worksheet=ws)

    class FakeClient:
        def open_by_key(self, key):
            return sh

    monkeypatch.setattr(gss.gspread, "service_account", lambda filename: FakeClient())

    iocs = [
        {"type": "ip", "value": "1.2.3.4", "source": "AbuseIPDB"},
        {"type": "domain", "value": "evil.com", "source": "Mallory"},
    ]
    gss.push_iocs_to_sheet(iocs)

    assert ws.appended_rows is not None
    assert len(ws.appended_rows) == 1
    assert ws.appended_rows[0][0] == "domain"
    assert ws.appended_rows[0][1] == "evil.com"


def test_push_iocs_creates_worksheet_if_missing(monkeypatch):
    _configure(monkeypatch)
    sh = FakeSpreadsheet(missing=True)

    class FakeClient:
        def open_by_key(self, key):
            return sh

    monkeypatch.setattr(gss.gspread, "service_account", lambda filename: FakeClient())

    gss.push_iocs_to_sheet([{"type": "ip", "value": "9.9.9.9"}])

    assert sh.added_worksheet is not None
    assert sh.added_worksheet.appended_header == gss.SHEET_HEADER
    assert sh.added_worksheet.appended_rows[0][0:2] == ["ip", "9.9.9.9"]


def test_push_iocs_swallows_exceptions(monkeypatch):
    _configure(monkeypatch)

    def raising_service_account(filename):
        raise RuntimeError("network down")

    monkeypatch.setattr(gss.gspread, "service_account", raising_service_account)

    # Should not raise
    gss.push_iocs_to_sheet([{"type": "ip", "value": "1.2.3.4"}])
