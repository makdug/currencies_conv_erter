from datetime import datetime, timedelta, timezone

import pytest

from currency.provider import ProviderError
from currency.service import RateService, ServiceError, as_iso, utc_now


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


class FallbackProvider:
    source_name = "csv"

    def __init__(self, pairs=None, intraday=None, daily=None, error=None):
        self.pairs = pairs or {}
        self.intraday = intraday
        self.daily = daily or {}
        self.error = error

    def fetch_grouped(self, day):
        if self.error:
            raise self.error
        return self.pairs

    def fetch_intraday(self, pair):
        if self.error:
            raise self.error
        if self.intraday is None:
            raise ProviderError("no_data")
        return self.intraday

    def fetch_daily(self, pair, days):
        if self.error:
            raise self.error
        if pair in self.daily:
            return self.daily[pair]
        raise ProviderError("no_data")


def test_as_iso_none():
    assert as_iso(None) is None


def test_get_operations(service):
    service.convert("USD", "EUR", "10")
    service.convert("USD", "USD", "5")
    operations = service.get_operations()
    assert len(operations) == 2
    assert operations[0]["to"] == "USD"
    assert operations[1]["to"] == "EUR"


@pytest.mark.parametrize("limit", ["abc", "0", "1000"])
def test_get_operations_invalid_limit(service, limit):
    with pytest.raises(ServiceError) as error:
        service.get_operations(limit)
    assert error.value.code == "invalid_limit"


def test_candidate_days_skips_weekends(provider, cache):
    monday = datetime(2026, 11, 23, tzinfo=timezone.utc)
    service = RateService(
        provider=provider,
        cache=cache,
        now=lambda: monday,
    )
    days = list(service._candidate_days())
    assert [day.isoformat() for day in days] == [
        "2026-11-20",
        "2026-11-19",
        "2026-11-18",
    ]


def test_rates_without_timestamps(service):
    service.provider.pairs = {"USDEUR": {"rate": 0.9}}
    result = service.get_rates("USD")
    assert result["as_of"] is None
    assert result["rates"]["EUR"] == pytest.approx(0.9)


def test_rates_fallback_provider(provider, cache, fixed_now):
    fallback = FallbackProvider(
        pairs={"USDEUR": {"rate": 0.9, "timestamp": 1}},
    )
    provider.error = ProviderError("network")
    service = RateService(
        provider=provider,
        cache=cache,
        fallback_provider=fallback,
        now=lambda: fixed_now,
    )
    result = service.get_rates("USD")
    assert result["source"] == "csv"
    assert result["rates"]["EUR"] == pytest.approx(0.9)


def test_rates_fallback_error_breaks(provider, cache, fixed_now):
    fallback = FallbackProvider(error=ProviderError("network"))
    provider.error = ProviderError("network")
    service = RateService(
        provider=provider,
        cache=cache,
        fallback_provider=fallback,
        now=lambda: fixed_now,
    )
    with pytest.raises(ServiceError) as error:
        service.get_rates("USD")
    assert error.value.code == "rates_unavailable"


def test_rates_fallback_error_continues(provider, cache, fixed_now):
    fallback = FallbackProvider(error=ProviderError("http_500"))
    provider.error = ProviderError("http_500")
    service = RateService(
        provider=provider,
        cache=cache,
        fallback_provider=fallback,
        now=lambda: fixed_now,
    )
    with pytest.raises(ServiceError) as error:
        service.get_rates("USD")
    assert error.value.code == "rates_unavailable"


def test_rates_empty_provider(provider, cache, fixed_now):
    provider.pairs = {}
    service = RateService(provider=provider, cache=cache, now=lambda: fixed_now)
    with pytest.raises(ServiceError) as error:
        service.get_rates("USD")
    assert error.value.code == "rates_unavailable"


def test_rates_primary_error_without_fallback_continues(
    provider, cache, fixed_now
):
    provider.error = ProviderError("http_500")
    service = RateService(provider=provider, cache=cache, now=lambda: fixed_now)
    with pytest.raises(ServiceError) as error:
        service.get_rates("USD")
    assert error.value.code == "rates_unavailable"


def test_convert_no_rate(provider, cache, fixed_now):
    provider.pairs = {"EURUSD": {"rate": 1.1, "timestamp": 1}}
    service = RateService(provider=provider, cache=cache, now=lambda: fixed_now)
    with pytest.raises(ServiceError) as error:
        service.convert("USD", "JPY", "1")
    assert error.value.code == "no_rate"


def test_convert_uses_fallback_intraday(provider, cache, fixed_now):
    fallback = FallbackProvider(
        intraday={"rate": 0.8, "timestamp": 1},
    )
    service = RateService(
        provider=provider,
        cache=cache,
        fallback_provider=fallback,
        now=lambda: fixed_now,
    )
    result = service.convert("USD", "EUR", "1")
    assert result["rate"] == 0.8
    assert result["source"] == "csv_intraday"


def test_convert_uses_cached_intraday_when_fallback_fails(
    provider, cache, fixed_now
):
    cache.save_pair(
        "USDEUR",
        {
            "rate": 0.7,
            "source_name": "massive",
            "fetched_at": as_iso(fixed_now),
        },
    )
    fallback = FallbackProvider()
    service = RateService(
        provider=provider,
        cache=cache,
        fallback_provider=fallback,
        intraday_ttl=0,
        now=lambda: fixed_now,
    )
    result = service.convert("USD", "EUR", "1")
    assert result["rate"] == 0.7
    assert result["source"] == "massive_intraday"


def test_history_uses_fallback_provider(provider, cache, fixed_now):
    fallback = FallbackProvider(
        daily={
            "USDEUR": [
                {"date": "2026-11-22", "rate": 0.9},
                {"date": "2026-11-23", "rate": 0.91},
            ]
        }
    )
    service = RateService(
        provider=provider,
        cache=cache,
        fallback_provider=fallback,
        now=lambda: fixed_now,
    )
    result = service.get_history("USD", "EUR", 7)
    assert result["source"] == "csv"
    assert len(result["points"]) == 2


def test_history_uses_fallback_cross(provider, cache, fixed_now):
    fallback = FallbackProvider(
        daily={
            "RUBUSD": [{"date": "2026-11-23", "rate": 0.012}],
            "AEDUSD": [{"date": "2026-11-23", "rate": 0.27}],
        }
    )
    service = RateService(
        provider=provider,
        cache=cache,
        fallback_provider=fallback,
        now=lambda: fixed_now,
    )
    result = service.get_history("RUB", "AED", 7)
    assert result["source"] == "csv_cross"
    assert result["points"][0]["rate"] == pytest.approx(0.012 / 0.27)


def test_history_uses_fallback_reverse(provider, cache, fixed_now):
    fallback = FallbackProvider(
        daily={
            "EURUSD": [{"date": "2026-11-23", "rate": 1.2}],
        }
    )
    service = RateService(
        provider=provider,
        cache=cache,
        fallback_provider=fallback,
        now=lambda: fixed_now,
    )
    result = service.get_history("USD", "EUR", 7)
    assert result["source"] == "csv_reverse"
    assert result["points"][0]["rate"] == pytest.approx(1 / 1.2)


def test_history_uses_fresh_cache(service):
    service.provider.daily = {
        "USDEUR": [{"date": "2026-11-23", "rate": 0.9}],
    }
    first = service.get_history("USD", "EUR", 7)
    service.provider.daily = {}
    second = service.get_history("USD", "EUR", 7)
    assert second == first


def test_history_returns_stale_cache(provider, cache, fixed_now):
    service = RateService(
        provider=provider,
        cache=cache,
        history_ttl=1,
        now=lambda: fixed_now,
    )
    service.provider.daily = {
        "USDEUR": [{"date": "2026-11-23", "rate": 0.9}],
    }
    first = service.get_history("USD", "EUR", 7)
    service.provider.daily = {}
    service.now = lambda: fixed_now + timedelta(seconds=10)
    second = service.get_history("USD", "EUR", 7)
    assert second["stale"] is True
    assert second["points"] == first["points"]


def test_fresh_invalid_values(service):
    assert service._fresh(None, 60) is False
    assert service._fresh("not-a-date", 60) is False


def test_build_graph_skips_zero_rate():
    assert RateService._build_graph({"USDEUR": {"rate": 0}}) == {}


def test_utc_now_returns_timezone_aware_datetime():
    moment = utc_now()
    assert moment.tzinfo is not None


def test_get_history_invalid_source(service):
    with pytest.raises(ServiceError) as error:
        service.get_history("XXX", "EUR", 7)
    assert error.value.code == "invalid_source"


def test_get_history_invalid_target(service):
    with pytest.raises(ServiceError) as error:
        service.get_history("USD", "XXX", 7)
    assert error.value.code == "invalid_target"


def test_convert_intraday_without_timestamp(provider, cache, fixed_now):
    provider.intraday = {"rate": 0.9}
    service = RateService(provider=provider, cache=cache, now=lambda: fixed_now)
    result = service.convert("USD", "EUR", "1")
    assert result["rate"] == 0.9
    assert result["as_of"] is None


def test_daily_points_handles_empty_primary(provider, cache, fixed_now):
    provider.daily = {"USDEUR": []}
    service = RateService(provider=provider, cache=cache, now=lambda: fixed_now)
    points, source = service._daily_points("USDEUR", 7)
    assert points == []
    assert source is None


def test_daily_points_handles_empty_fallback(provider, cache, fixed_now):
    fallback = FallbackProvider(daily={"USDEUR": []})
    service = RateService(
        provider=provider,
        cache=cache,
        fallback_provider=fallback,
        now=lambda: fixed_now,
    )
    points, source = service._daily_points("USDEUR", 7)
    assert points == []
    assert source is None


def test_history_cross_with_missing_target(provider, cache, fixed_now):
    provider.daily = {
        "RUBUSD": [{"date": "2026-11-23", "rate": 0.012}],
    }
    service = RateService(provider=provider, cache=cache, now=lambda: fixed_now)
    with pytest.raises(ServiceError) as error:
        service.get_history("RUB", "AED", 7)
    assert error.value.code == "history_unavailable"


def test_history_cross_without_matching_dates(provider, cache, fixed_now):
    provider.daily = {
        "RUBUSD": [{"date": "2026-11-23", "rate": 0.012}],
        "AEDUSD": [{"date": "2026-11-22", "rate": 0.27}],
    }
    service = RateService(provider=provider, cache=cache, now=lambda: fixed_now)
    with pytest.raises(ServiceError) as error:
        service.get_history("RUB", "AED", 7)
    assert error.value.code == "history_unavailable"


def test_convert_uses_fresh_cached_intraday(provider, cache, fixed_now):
    cache.save_pair(
        "USDEUR",
        {
            "rate": 0.7,
            "source_name": "massive",
            "fetched_at": as_iso(fixed_now),
        },
    )
    service = RateService(provider=provider, cache=cache, now=lambda: fixed_now)
    result = service.convert("USD", "EUR", "1")
    assert result["rate"] == 0.7
    assert result["source"] == "massive_intraday"
