import pytest

from currency.csv_provider import CsvRateProvider
from currency.provider import ProviderError


def write_csv(tmp_path, text):
    path = tmp_path / "rates.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_csv_provider_loads_and_reads(tmp_path):
    path = write_csv(
        tmp_path,
        "base,quote,rate\nUSD,EUR,0.9\nUSD,GBP,0.8\n",
    )
    provider = CsvRateProvider(path)
    assert provider.source_name == "csv"
    assert provider.fetch_grouped("2026-11-24")["USDEUR"]["rate"] == 0.9
    assert provider.fetch_intraday("USDEUR")["rate"] == 0.9
    assert provider.fetch_daily("USDEUR", 7) == [
        {"date": "csv", "rate": 0.9}
    ]
    with pytest.raises(ProviderError, match="no_data"):
        provider.fetch_intraday("EURUSD")
    assert provider.fetch_daily("EURUSD", 7) == []


def test_csv_provider_missing_file(tmp_path):
    with pytest.raises(ProviderError, match="csv_not_found"):
        CsvRateProvider(tmp_path / "missing.csv")


def test_csv_provider_invalid_number(tmp_path):
    path = write_csv(
        tmp_path,
        "base,quote,rate\nUSD,EUR,not-a-number\n",
    )
    with pytest.raises(ProviderError, match="csv_invalid"):
        CsvRateProvider(path)


def test_csv_provider_skips_empty_rows(tmp_path):
    path = write_csv(
        tmp_path,
        "base,quote,rate\nUSD,EUR,\nUSD,GBP,0.8\n",
    )
    provider = CsvRateProvider(path)
    assert "USDEUR" not in provider.pairs
    assert "USDGBP" in provider.pairs
