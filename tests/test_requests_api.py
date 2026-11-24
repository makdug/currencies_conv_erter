import os
import socket
import threading
import time

import pytest
import requests
from werkzeug.serving import make_server

BASE_URL = "http://127.0.0.1:8008"


def _port_is_open():
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", 8008)) == 0


@pytest.fixture(scope="session", autouse=True)
def live_server(tmp_path_factory):
    if _port_is_open():
        yield BASE_URL
        return

    os.environ["RATES_SOURCE"] = "csv"
    os.environ["MONGO_URL"] = ""
    os.environ["CACHE_PATH"] = str(
        tmp_path_factory.mktemp("live") / "cache.json"
    )
    os.environ["CSV_RATES_PATH"] = "currency/rates.csv"

    from server import create_app

    app = create_app()
    server = make_server("127.0.0.1", 8008, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    for _ in range(50):
        try:
            requests.get(f"{BASE_URL}/api/health", timeout=0.2)
            break
        except requests.RequestException:
            time.sleep(0.1)

    yield BASE_URL

    server.shutdown()
    thread.join(timeout=2)


def test_health(live_server):
    response = requests.get(f"{live_server}/api/health", timeout=5)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_convert(live_server):
    response = requests.get(
        f"{live_server}/api/convert",
        params={"from": "USD", "to": "EUR", "amount": 100},
        timeout=5,
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["from"] == "USD"
    assert payload["to"] == "EUR"
    assert payload["result"] > 0


def test_operations(live_server):
    requests.get(
        f"{live_server}/api/convert",
        params={"from": "USD", "to": "EUR", "amount": 1},
        timeout=5,
    )
    response = requests.get(f"{live_server}/api/operations", timeout=5)
    payload = response.json()
    assert response.status_code == 200
    assert "operations" in payload
    assert payload["operations"]


def test_negative_amount(live_server):
    response = requests.get(
        f"{live_server}/api/convert",
        params={"from": "USD", "to": "EUR", "amount": -1},
        timeout=5,
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_amount"
