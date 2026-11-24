import pytest

from currency.service import ServiceError
from server import create_app


class FakeCache:
    def info(self):
        return {"has_rates": True, "as_of": "2026-11-23T23:59:59Z"}


class FakeService:
    def __init__(self):
        self.cache = FakeCache()
        self.provider_name = "massive"

    def get_operations(self, limit=50):
        if int(limit) < 1:
            raise ServiceError("Плохой лимит", "invalid_limit", 400)
        return [
            {
                "id": "op-1",
                "from": "USD",
                "to": "EUR",
                "amount": 10,
                "limit": int(limit),
            }
        ]

    def get_currencies(self):
        return [
            {
                "code": "USD",
                "name_en": "United States dollar",
                "name_ru": "Доллар США",
            }
        ]

    def get_rates(self, base):
        if base == "BAD":
            raise ServiceError("Плохая база", "invalid_base", 400)
        return {"base": base, "rates": {"USD": 1.0}, "stale": False}

    def convert(self, source, target, amount):
        if source == "BAD":
            raise ServiceError("Плохая валюта", "invalid_source", 400)
        return {
            "from": source,
            "to": target,
            "amount": float(amount),
            "rate": 1.0,
            "result": float(amount),
            "stale": False,
        }

    def get_history(self, source, target, days):
        if source == "BAD":
            raise ServiceError("Нет истории", "history_unavailable", 503)
        return {
            "from": source,
            "to": target,
            "days": int(days),
            "points": [],
            "stale": False,
        }


@pytest.fixture
def client():
    app = create_app(service=FakeService())
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Конвертер валют" in response.get_data(as_text=True)


def test_currencies(client):
    response = client.get("/api/currencies")
    assert response.status_code == 200
    assert response.get_json()["currencies"][0]["code"] == "USD"


def test_rates(client):
    response = client.get("/api/rates?base=EUR")
    assert response.status_code == 200
    assert response.get_json()["base"] == "EUR"


def test_rates_error(client):
    response = client.get("/api/rates?base=BAD")
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_base"


def test_convert(client):
    response = client.get("/api/convert?from=USD&to=EUR&amount=100")
    assert response.status_code == 200
    assert response.get_json()["result"] == 100.0


def test_convert_error(client):
    response = client.get("/api/convert?from=BAD&to=EUR&amount=1")
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_source"


def test_history(client):
    response = client.get("/api/history?from=USD&to=EUR&days=7")
    assert response.status_code == 200
    assert response.get_json()["days"] == 7


def test_history_error(client):
    response = client.get("/api/history?from=BAD&to=EUR&days=7")
    assert response.status_code == 503
    assert response.get_json()["error"] == "history_unavailable"


def test_operations(client):
    response = client.get("/api/operations?limit=10")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["operations"][0]["id"] == "op-1"
    assert payload["operations"][0]["limit"] == 10


def test_operations_invalid_limit(client):
    response = client.get("/api/operations?limit=0")
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_limit"


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["provider"] == "massive"
    assert payload["cache"]["has_rates"] is True
