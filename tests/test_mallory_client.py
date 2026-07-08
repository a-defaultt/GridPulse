import json

import pytest
from malloryapi import RateLimitError

from src.aggregator import mallory_client


def test_fetch_recent_iocs_no_api_key(monkeypatch):
    monkeypatch.setattr(mallory_client, "MALLORY_API_KEY", None)
    assert mallory_client.fetch_recent_iocs() == []


def test_fetch_recent_iocs_uses_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(mallory_client, "MALLORY_API_KEY", "sk-test")
    cache_file = tmp_path / "mallory_cache.json"
    today = mallory_client.utc_now().strftime("%Y-%m-%d")
    cache_file.write_text(json.dumps({"date": today, "iocs": [{"ioc_value": "1.2.3.4", "ioc_type": "ip"}]}))
    monkeypatch.setattr(mallory_client, "CACHE_FILE", str(cache_file))

    class ExplodingClient:
        def __init__(self, *a, **k):
            raise AssertionError("SDK should not be instantiated when cache is fresh")

    monkeypatch.setattr(mallory_client, "MalloryApi", ExplodingClient)

    result = mallory_client.fetch_recent_iocs()
    assert result == [{"ioc_value": "1.2.3.4", "ioc_type": "ip"}]


def test_fetch_recent_iocs_handles_sdk_exception(monkeypatch, tmp_path):
    monkeypatch.setattr(mallory_client, "MALLORY_API_KEY", "sk-test")
    monkeypatch.setattr(mallory_client, "CACHE_FILE", str(tmp_path / "mallory_cache.json"))

    class BrokenObservables:
        def list(self, **kwargs):
            raise RuntimeError("boom")

    class BrokenClient:
        def __init__(self, *a, **k):
            self.observables = BrokenObservables()

    monkeypatch.setattr(mallory_client, "MalloryApi", BrokenClient)

    assert mallory_client.fetch_recent_iocs() == []


def test_enrich_iocs_respects_limit(monkeypatch):
    monkeypatch.setattr(mallory_client, "MALLORY_API_KEY", "sk-test")
    calls = []

    def fake_enrich_ioc(value, typ):
        calls.append((typ, value))
        return {"confidence": 80, "tags": ["botnet"], "context": "seen in the wild"}

    monkeypatch.setattr(mallory_client, "enrich_ioc", fake_enrich_ioc)

    iocs = [
        {"ioc_type": "ip", "ioc_value": f"1.1.1.{i}"} for i in range(5)
    ]
    result = mallory_client.enrich_iocs(iocs, limit=2)

    assert len(calls) == 2
    enriched = [r for r in result if "mallory_tags" in r]
    assert len(enriched) == 2
    not_enriched = [r for r in result if "mallory_tags" not in r]
    assert len(not_enriched) == 3


def test_enrich_iocs_dedups_across_sources(monkeypatch):
    monkeypatch.setattr(mallory_client, "MALLORY_API_KEY", "sk-test")
    calls = []

    def fake_enrich_ioc(value, typ):
        calls.append((typ, value))
        return {"confidence": 50, "tags": [], "context": ""}

    monkeypatch.setattr(mallory_client, "enrich_ioc", fake_enrich_ioc)

    iocs = [
        {"ioc_type": "ip", "ioc_value": "8.8.8.8", "source": "AbuseIPDB"},
        {"ioc_type": "ip", "ioc_value": "8.8.8.8", "source": "article_extraction"},
    ]
    result = mallory_client.enrich_iocs(iocs, limit=10)

    assert len(calls) == 1
    assert all(r["confidence"] == 50 for r in result)


def test_enrich_iocs_no_api_key(monkeypatch):
    monkeypatch.setattr(mallory_client, "MALLORY_API_KEY", None)
    iocs = [{"ioc_type": "ip", "ioc_value": "1.2.3.4"}]
    assert mallory_client.enrich_iocs(iocs) == iocs


def test_enrich_ioc_not_found_returns_none(monkeypatch):
    from malloryapi import NotFoundError

    monkeypatch.setattr(mallory_client, "MALLORY_API_KEY", "sk-test")

    class NotFoundObservables:
        def get_by_type_name(self, typ, val):
            raise NotFoundError("not found", status_code=404, response_body="")

    class FakeClient:
        def __init__(self, *a, **k):
            self.observables = NotFoundObservables()

    monkeypatch.setattr(mallory_client, "MalloryApi", FakeClient)

    assert mallory_client.enrich_ioc("evil.com", "domain") is None


def test_to_mallory_type_maps_gridpulse_vocabulary():
    assert mallory_client._to_mallory_type("ip", "1.2.3.4") == "ip.v4"
    assert mallory_client._to_mallory_type("ip_address", "1.2.3.4") == "ip.v4"
    assert mallory_client._to_mallory_type("ip", "2001:db8::1") == "ip.v6"
    assert mallory_client._to_mallory_type("url", "https://evil.com/x") == "uri"
    assert mallory_client._to_mallory_type("md5", "abc") == "hash.md5"
    assert mallory_client._to_mallory_type("sha1", "abc") == "hash.sha1"
    assert mallory_client._to_mallory_type("sha256", "abc") == "hash.sha256"
    assert mallory_client._to_mallory_type("domain", "evil.com") == "domain"


def test_enrich_ioc_uses_mapped_type_for_ip_lookup(monkeypatch):
    monkeypatch.setattr(mallory_client, "MALLORY_API_KEY", "sk-test")
    seen_types = []

    class RecordingObservables:
        def get_by_type_name(self, typ, val):
            seen_types.append(typ)
            return {"tags": [], "description": None}

        def opinions_by_type_name(self, typ, val, limit=1):
            return []

    class FakeClient:
        def __init__(self, *a, **k):
            self.observables = RecordingObservables()

    monkeypatch.setattr(mallory_client, "MalloryApi", FakeClient)

    mallory_client.enrich_ioc("1.2.3.4", "ip")
    assert seen_types == ["ip.v4"]
