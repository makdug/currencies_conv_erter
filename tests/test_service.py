from datetime import timedelta

import pytest

from currency.provider import ProviderError
from currency.service import RateService, ServiceError


def test_get_rates_returns_all_currencies(service):
    result = service.get_rates("USD")
    assert result["base"] == "USD"
    assert result["rates"]["USD"] == 1.0
    assert result["rates"]["EUR"] == pytest.approx(1 / 1.1)
    assert result["rates"]["JPY"] == pytest.approx(150.0)
    assert result["rates"]["GBP"] == pytest.approx(1 / 1.25)
    assert result["stale"] is False
    assert result["source"] == "massive"


def test_get_rates_invalid_base(service):
    with pytest.raises(ServiceError) as error:
        service.get_rates("XXX")
    assert error.value.code == "invalid_base"
    assert error.value.status == 400


def test_convert_direct(service):
    service.provider.intraday = {"rate": 0.9, "timestamp": 1795478399999}
    result = service.convert("USD", "EUR", "100")
    assert result["from"] == "USD"
    assert result["to"] == "EUR"
    assert result["amount"] == 100.0
    assert result["rate"] == 0.9
    assert result["result"] == 90.0
    assert result["source"] == "massive_intraday"
    assert result["stale"] is False


def test_convert_cross_without_intraday(service):
    result = service.convert("EUR", "JPY", "2")
    assert result["rate"] == pytest.approx(1.1 * 150.0)
    assert result["result"] == pytest.approx(2 * 1.1 * 150.0)
    assert result["path"] == ["EUR", "USD", "JPY"]
    assert result["source"] == "massive"


def test_convert_same_currency(service):
    result = service.convert("USD", "USD", "5")
    assert result["rate"] == 1.0
    assert result["result"] == 5.0
    assert result["path"] == ["USD"]


@pytest.mark.parametrize("amount", ["abc", "-1", "0", None])
def test_convert_invalid_amount(service, amount):
    with pytest.raises(ServiceError) as error:
        service.convert("USD", "EUR", amount)
    assert error.value.code == "invalid_amount"


def test_convert_invalid_source(service):
    with pytest.raises(ServiceError) as error:
        service.convert("XXX", "EUR", "1")
    assert error.value.code == "invalid_source"


def test_convert_invalid_target(service):
    with pytest.raises(ServiceError) as error:
        service.convert("USD", "XXX", "1")
    assert error.value.code == "invalid_target"


def test_get_history(service):
    service.provider.daily = {
        "USDEUR": [
            {"date": "2026-11-22", "rate": 0.9},
            {"date": "2026-11-23", "rate": 0.91},
        ]
    }
    result = service.get_history("USD", "EUR", 7)
    assert result["from"] == "USD"
    assert result["to"] == "EUR"
    assert result["days"] == 7
    assert result["points"] == [
        {"date": "2026-11-22", "rate": 0.9},
        {"date": "2026-11-23", "rate": 0.91},
    ]
    assert result["source"] == "massive"
    assert result["stale"] is False


def test_get_history_reverse(service):
    service.provider.daily = {
        "EURUSD": [
            {"date": "2026-11-22", "rate": 1.1},
            {"date": "2026-11-23", "rate": 1.2},
        ]
    }
    result = service.get_history("USD", "EUR", 7)
    assert result["points"] == [
        {"date": "2026-11-22", "rate": pytest.approx(1 / 1.1)},
        {"date": "2026-11-23", "rate": pytest.approx(1 / 1.2)},
    ]
    assert result["source"] == "massive_reverse"


def test_get_history_cross(service):
    service.provider.daily = {
        "RUBUSD": [
            {"date": "2026-11-22", "rate": 0.012},
            {"date": "2026-11-23", "rate": 0.013},
        ],
        "AEDUSD": [
            {"date": "2026-11-22", "rate": 0.27},
            {"date": "2026-11-23", "rate": 0.272},
        ],
    }
    result = service.get_history("RUB", "AED", 7)
    assert result["source"] == "massive_cross"
    assert result["points"][0]["rate"] == pytest.approx(0.012 / 0.27)
    assert result["points"][1]["rate"] == pytest.approx(0.013 / 0.272)


def test_get_history_same_currency(service):
    result = service.get_history("USD", "USD", 3)
    assert result["source"] == "local"
    assert len(result["points"]) == 3
    assert all(point["rate"] == 1.0 for point in result["points"])


@pytest.mark.parametrize("days", ["abc", "0", "32"])
def test_get_history_invalid_days(service, days):
    with pytest.raises(ServiceError) as error:
        service.get_history("USD", "EUR", days)
    assert error.value.code == "invalid_days"


def test_rates_fallback_to_fresh_cache(service):
    first = service.get_rates("USD")
    assert first["stale"] is False
    service.provider.error = ProviderError("network")
    second = service.get_rates("USD")
    assert second["stale"] is False
    assert second["source"] == "massive"


def test_rates_stale_cache(provider, cache, fixed_now):
    service = RateService(
        provider=provider,
        cache=cache,
        rates_ttl=1,
        now=lambda: fixed_now,
    )
    first = service.get_rates("USD")
    assert first["stale"] is False
    provider.error = ProviderError("network")
    service.now = lambda: fixed_now + timedelta(seconds=10)
    second = service.get_rates("USD")
    assert second["stale"] is True
    assert second["source"] == "cache"


def test_rates_unavailable(provider, cache, fixed_now):
    provider.error = ProviderError("network")
    service = RateService(provider=provider, cache=cache, now=lambda: fixed_now)
    with pytest.raises(ServiceError) as error:
        service.get_rates("USD")
    assert error.value.code == "rates_unavailable"
    assert error.value.status == 503


def test_history_unavailable(provider, cache, fixed_now):
    service = RateService(provider=provider, cache=cache, now=lambda: fixed_now)
    with pytest.raises(ServiceError) as error:
        service.get_history("USD", "EUR", 7)
    assert error.value.code == "history_unavailable"
    assert error.value.status == 503


def test_get_currencies(service):
    currencies = service.get_currencies()
    assert len(currencies) > 100
    assert any(currency["code"] == "USD" for currency in currencies)


def test_history_cache_key_includes_days(service):
    service.provider.daily = {
        "USDEUR": [{"date": "2026-11-23", "rate": 0.9}],
    }
    service.get_history("USD", "EUR", 7)
    service.get_history("USD", "EUR", 14)
    assert service.cache.get_history("USDEUR:7") is not None
    assert service.cache.get_history("USDEUR:14") is not None
