import pytest

from currency.cache import JsonCache, MongoCache


def test_json_cache_roundtrip(tmp_path):
    cache = JsonCache(tmp_path / "cache.json")
    assert cache.get_rates() is None

    cache.save_rates(
        {
            "pairs": {"EURUSD": {"rate": 1.1}},
            "as_of": "2026-11-23T23:59:59Z",
        }
    )
    assert cache.get_rates()["pairs"]["EURUSD"]["rate"] == 1.1

    cache.save_pair("EURUSD", {"rate": 1.2})
    assert cache.get_pair("EURUSD")["rate"] == 1.2

    cache.save_history("EURUSD:7", {"points": []})
    assert cache.get_history("EURUSD:7")["points"] == []

    info = cache.info()
    assert info["has_rates"] is True
    assert info["path"].endswith("cache.json")


def test_mongo_cache_is_a_stub():
    with pytest.raises(NotImplementedError):
        MongoCache("mongodb://localhost:27017")
