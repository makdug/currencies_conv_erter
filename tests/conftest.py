from datetime import datetime, timezone

import pytest

from currency.cache import JsonCache
from currency.provider import ProviderError
from currency.service import RateService


class FakeProvider:
    source_name = "massive"

    def __init__(self, pairs=None, intraday=None, daily=None, error=None):
        self.pairs = pairs or {}
        self.intraday = intraday
        self.daily = daily or {}
        self.error = error
        self.calls = []

    def fetch_grouped(self, day):
        self.calls.append(("grouped", day))
        if self.error:
            raise self.error
        return self.pairs

    def fetch_intraday(self, pair):
        self.calls.append(("intraday", pair))
        if self.intraday is None:
            raise ProviderError("no_data")
        return self.intraday

    def fetch_daily(self, pair, days=7):
        self.calls.append(("daily", pair, days))
        if pair in self.daily:
            return self.daily[pair]
        raise ProviderError("no_data")


@pytest.fixture
def fixed_now():
    return datetime(2026, 11, 24, 0, 42, tzinfo=timezone.utc)


@pytest.fixture
def cache(tmp_path):
    return JsonCache(tmp_path / "cache.json")


@pytest.fixture
def pairs():
    return {
        "EURUSD": {"rate": 1.1, "timestamp": 1795478399999},
        "USDJPY": {"rate": 150.0, "timestamp": 1795478399999},
        "GBPUSD": {"rate": 1.25, "timestamp": 1795478399999},
    }


@pytest.fixture
def provider(pairs):
    return FakeProvider(pairs=pairs)


@pytest.fixture
def service(provider, cache, fixed_now):
    return RateService(
        provider=provider,
        cache=cache,
        rates_ttl=300,
        intraday_ttl=60,
        history_ttl=300,
        now=lambda: fixed_now,
    )
