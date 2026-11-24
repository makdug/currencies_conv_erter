from currency.cache import JsonCache
from currency.csv_provider import CsvRateProvider
from currency.factory import create_service, create_storage
from currency.provider import MassiveProvider


def make_csv(tmp_path):
    path = tmp_path / "rates.csv"
    path.write_text(
        "base,quote,rate\nUSD,EUR,0.9\n",
        encoding="utf-8",
    )
    return path


def test_create_storage_json(monkeypatch, tmp_path):
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.setenv("CACHE_PATH", str(tmp_path / "cache.json"))
    storage = create_storage()
    assert isinstance(storage, JsonCache)


def test_create_storage_mongo(monkeypatch):
    class FakeMongo:
        def __init__(self, url, db):
            self.url = url
            self.db = db

    monkeypatch.setenv("MONGO_URL", "mongodb://test")
    monkeypatch.setenv("MONGO_DB", "testdb")
    monkeypatch.setattr("currency.factory.MongoCache", FakeMongo)
    storage = create_storage()
    assert isinstance(storage, FakeMongo)
    assert storage.url == "mongodb://test"
    assert storage.db == "testdb"


def test_create_service_uses_csv_when_requested(monkeypatch, tmp_path):
    monkeypatch.setenv("RATES_SOURCE", "csv")
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key")
    monkeypatch.setenv("CSV_RATES_PATH", str(make_csv(tmp_path)))
    monkeypatch.setenv("CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.delenv("MONGO_URL", raising=False)

    service = create_service()
    assert isinstance(service.provider, CsvRateProvider)
    assert service.fallback_provider is None
    assert isinstance(service.cache, JsonCache)
    assert service.get_rates("USD")["rates"]["EUR"] == 0.9


def test_create_service_uses_massive_with_csv_fallback(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RATES_SOURCE", "auto")
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key")
    monkeypatch.setenv("CSV_RATES_PATH", str(make_csv(tmp_path)))
    monkeypatch.setenv("CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.delenv("MONGO_URL", raising=False)

    service = create_service()
    assert isinstance(service.provider, MassiveProvider)
    assert isinstance(service.fallback_provider, CsvRateProvider)


def test_create_service_without_key_uses_csv(monkeypatch, tmp_path):
    monkeypatch.setenv("RATES_SOURCE", "auto")
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.setenv("CSV_RATES_PATH", str(make_csv(tmp_path)))
    monkeypatch.setenv("CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.delenv("MONGO_URL", raising=False)

    service = create_service()
    assert isinstance(service.provider, CsvRateProvider)
    assert service.fallback_provider is None
