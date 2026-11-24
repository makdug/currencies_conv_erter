import pytest
from mongomock import MongoClient

from currency.cache import JsonCache, MongoCache


def test_json_cache_roundtrip(tmp_path):
    cache = JsonCache(tmp_path / "cache.json")
    assert cache.get_rates() is None
    assert cache.get_pair("EURUSD") is None
    assert cache.get_history("USDEUR:7") is None
    assert cache.get_operations() == []

    cache.save_rates(
        {
            "pairs": {"EURUSD": {"rate": 1.1}},
            "as_of": "2026-11-23",
        }
    )
    cache.save_pair("EURUSD", {"rate": 1.2})
    cache.save_history("USDEUR:7", {"points": []})
    cache.add_operation(
        {
            "id": "op-1",
            "timestamp": "2026-11-24T00:00:00Z",
            "amount": 10,
        }
    )

    assert cache.get_rates()["as_of"] == "2026-11-23"
    assert cache.get_pair("EURUSD")["rate"] == 1.2
    assert cache.get_history("USDEUR:7")["points"] == []
    assert cache.get_operations()[0]["id"] == "op-1"

    info = cache.info()
    assert info["has_rates"] is True
    assert info["backend"] == "json"
    assert info["operations_count"] == 1
    assert info["path"].endswith("cache.json")


def test_json_cache_ignores_broken_json(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text("{broken", encoding="utf-8")
    cache = JsonCache(path)
    assert cache.get_rates() is None


def test_json_cache_removes_temp_file_on_error(tmp_path, monkeypatch):
    cache = JsonCache(tmp_path / "cache.json")

    def fail_replace(*args, **kwargs):
        raise OSError("disk is full")

    monkeypatch.setattr("currency.cache.os.replace", fail_replace)
    with pytest.raises(OSError):
        cache.save_rates({"pairs": {}})
    assert list(tmp_path.glob("*.tmp")) == []


def test_mongo_cache_roundtrip():
    cache = MongoCache(
        "mongodb://localhost",
        client=MongoClient(),
    )
    assert cache.get_rates() is None
    assert cache.get_pair("EURUSD") is None
    assert cache.get_history("USDEUR:7") is None
    assert cache.get_operations() == []

    cache.save_rates({"as_of": "2026-11-23"})
    cache.save_pair("EURUSD", {"rate": 1.2})
    cache.save_history("USDEUR:7", {"points": []})
    cache.add_operation(
        {
            "id": "op-1",
            "timestamp": "2026-11-24T00:00:00Z",
            "amount": 10,
        }
    )
    cache.add_operation(
        {
            "id": "op-2",
            "timestamp": "2026-11-24T01:00:00Z",
            "amount": 20,
        }
    )

    assert cache.get_rates()["as_of"] == "2026-11-23"
    assert cache.get_pair("EURUSD")["rate"] == 1.2
    assert cache.get_history("USDEUR:7")["points"] == []
    operations = cache.get_operations()
    assert [item["id"] for item in operations] == ["op-2", "op-1"]
    assert cache.get_operations(limit=1)[0]["id"] == "op-2"

    info = cache.info()
    assert info["has_rates"] is True
    assert info["backend"] == "mongodb"
    assert info["operations_count"] == 2


def test_mongo_cache_uses_default_client(monkeypatch):
    client = MongoClient()

    def fake_client(url):
        assert url == "mongodb://example"
        return client

    monkeypatch.setattr("currency.cache.MongoClient", fake_client)
    cache = MongoCache("mongodb://example")
    assert cache.client is client
    assert cache.info()["has_rates"] is False
