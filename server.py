import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from currency.cache import JsonCache
from currency.catalog import CURRENCIES
from currency.provider import MassiveProvider
from currency.service import RateService, ServiceError

load_dotenv()

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8008"))


def create_service():
    api_key = os.getenv("MASSIVE_API_KEY")
    if not api_key:
        raise RuntimeError("Не задан MASSIVE_API_KEY в .env")
    provider = MassiveProvider(
        api_key=api_key,
        base_url=os.getenv("MASSIVE_BASE_URL", "https://api.massive.com"),
        timeout=int(os.getenv("REQUEST_TIMEOUT", "20")),
    )
    cache = JsonCache(os.getenv("CACHE_PATH", "data/cache.json"))
    return RateService(
        provider=provider,
        cache=cache,
        rates_ttl=int(os.getenv("RATES_TTL", "300")),
        intraday_ttl=int(os.getenv("INTRADAY_TTL", "60")),
        history_ttl=int(os.getenv("HISTORY_TTL", "300")),
    )


def create_app(service=None):
    app = Flask(__name__)
    app.json.ensure_ascii = False
    if service is None:
        service = create_service()

    @app.get("/")
    def index():
        return render_template("index.html", currencies=CURRENCIES)

    @app.get("/api/currencies")
    def currencies():
        return jsonify({"currencies": service.get_currencies()})

    @app.get("/api/rates")
    def rates():
        try:
            return jsonify(service.get_rates(request.args.get("base", "USD")))
        except ServiceError as error:
            return jsonify({"error": error.code, "message": error.message}), (
                error.status
            )

    @app.get("/api/convert")
    def convert():
        try:
            return jsonify(
                service.convert(
                    request.args.get("from", "USD"),
                    request.args.get("to", "EUR"),
                    request.args.get("amount", "1"),
                )
            )
        except ServiceError as error:
            return jsonify({"error": error.code, "message": error.message}), (
                error.status
            )

    @app.get("/api/history")
    def history():
        try:
            return jsonify(
                service.get_history(
                    request.args.get("from", "USD"),
                    request.args.get("to", "EUR"),
                    request.args.get("days", "7"),
                )
            )
        except ServiceError as error:
            return jsonify({"error": error.code, "message": error.message}), (
                error.status
            )

    @app.get("/api/health")
    def health():
        cache_info = {}
        if hasattr(service, "cache") and hasattr(service.cache, "info"):
            cache_info = service.cache.info()
        return jsonify(
            {
                "status": "ok",
                "provider": "massive",
                "cache": cache_info,
            }
        )

    return app


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    create_app().run(host=HOST, port=PORT, debug=debug)
