import pytest
import requests

from currency.provider import MassiveProvider, ProviderError


class FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self.payload = payload or {}
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if self.error:
            raise self.error
        return self.response


def make_provider(session):
    return MassiveProvider(
        api_key="test-key",
        base_url="https://example.test",
        timeout=5,
        session=session,
    )


def test_fetch_grouped_parses_pairs():
    session = FakeSession(
        FakeResponse(
            payload={
                "results": [
                    {"T": "C:EURUSD", "c": 1.1, "t": 123},
                    {"T": "C:XAUUSD", "c": 2000, "t": 123},
                    {"T": "C:USDJPY", "c": None, "t": 123},
                ]
            }
        )
    )
    provider = make_provider(session)
    pairs = provider.fetch_grouped("2026-11-23")
    assert pairs == {"EURUSD": {"rate": 1.1, "timestamp": 123}}
    assert session.calls[0][1]["apiKey"] == "test-key"
    assert "/v2/aggs/grouped/locale/global/market/forex/2026-11-23" in (
        session.calls[0][0]
    )


def test_fetch_grouped_skips_short_tickers():
    session = FakeSession(
        FakeResponse(
            payload={
                "results": [
                    {"T": "C:EUR", "c": 1.1, "t": 123},
                    {"T": "C:EURUSD", "c": 1.1, "t": 123},
                ]
            }
        )
    )
    provider = make_provider(session)
    assert list(provider.fetch_grouped("2026-11-23")) == ["EURUSD"]


def test_fetch_intraday_returns_last_bar():
    session = FakeSession(
        FakeResponse(payload={"results": [{"c": 0.91, "t": 456}]})
    )
    provider = make_provider(session)
    row = provider.fetch_intraday("EURUSD")
    assert row == {"rate": 0.91, "timestamp": 456}
    assert "/v2/aggs/ticker/C:EURUSD/range/1/minute/" in session.calls[0][0]


def test_fetch_intraday_no_data():
    session = FakeSession(FakeResponse(payload={"results": []}))
    provider = make_provider(session)
    with pytest.raises(ProviderError, match="no_data"):
        provider.fetch_intraday("EURUSD")


def test_fetch_daily_returns_points():
    session = FakeSession(
        FakeResponse(
            payload={
                "results": [
                    {"c": 1.1, "t": 1795219199999},
                    {"c": 1.2, "t": 1795305599999},
                ]
            }
        )
    )
    provider = make_provider(session)
    points = provider.fetch_daily("EURUSD", 7)
    assert points == [
        {"date": "2026-11-20", "rate": 1.1},
        {"date": "2026-11-21", "rate": 1.2},
    ]


def test_get_raises_on_rate_limit():
    session = FakeSession(FakeResponse(status_code=429))
    with pytest.raises(ProviderError, match="rate_limit"):
        make_provider(session).fetch_grouped("2026-11-23")


def test_get_raises_on_http_error():
    session = FakeSession(FakeResponse(status_code=404))
    with pytest.raises(ProviderError, match="http_404"):
        make_provider(session).fetch_grouped("2026-11-23")


def test_get_raises_on_timeout():
    session = FakeSession(error=requests.Timeout())
    with pytest.raises(ProviderError, match="timeout"):
        make_provider(session).fetch_grouped("2026-11-23")


def test_get_raises_on_network_error():
    session = FakeSession(error=requests.ConnectionError())
    with pytest.raises(ProviderError, match="network"):
        make_provider(session).fetch_grouped("2026-11-23")


def test_get_raises_on_bad_json():
    session = FakeSession(FakeResponse(json_error=ValueError("bad")))
    with pytest.raises(ProviderError, match="bad_json"):
        make_provider(session).fetch_grouped("2026-11-23")


def test_get_raises_on_api_error():
    session = FakeSession(
        FakeResponse(payload={"status": "ERROR", "error": "test error"})
    )
    with pytest.raises(ProviderError, match="test error"):
        make_provider(session).fetch_grouped("2026-11-23")


def test_get_raises_on_not_authorized():
    session = FakeSession(
        FakeResponse(payload={"status": "NOT_AUTHORIZED"})
    )
    with pytest.raises(ProviderError, match="not_authorized"):
        make_provider(session).fetch_grouped("2026-11-23")


def test_provider_creates_default_session():
    provider = MassiveProvider(api_key="test-key")
    assert provider.session is not None


def test_get_without_params():
    session = FakeSession(FakeResponse(payload={"status": "OK"}))
    provider = make_provider(session)
    assert provider._get("/test") == {"status": "OK"}


def test_fetch_grouped_without_results():
    session = FakeSession(FakeResponse(payload={}))
    provider = make_provider(session)
    assert provider.fetch_grouped("2026-11-23") == {}


def test_fetch_daily_skips_incomplete_rows():
    session = FakeSession(
        FakeResponse(
            payload={
                "results": [
                    {"c": None, "t": 1},
                    {"c": 1.1, "t": None},
                    {"c": 1.2, "t": 1795305599999},
                ]
            }
        )
    )
    provider = make_provider(session)
    assert provider.fetch_daily("EURUSD", 7) == [
        {"date": "2026-11-21", "rate": 1.2}
    ]


def test_fetch_daily_without_results():
    session = FakeSession(FakeResponse(payload={}))
    provider = make_provider(session)
    assert provider.fetch_daily("EURUSD", 7) == []


def test_get_raises_on_api_error_without_message():
    session = FakeSession(FakeResponse(payload={"status": "ERROR"}))
    with pytest.raises(ProviderError, match="api_error"):
        make_provider(session).fetch_grouped("2026-11-23")
