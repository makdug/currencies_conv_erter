import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from currency.catalog import CURRENCIES
from currency.factory import create_service
from currency.service import ServiceError

load_dotenv()

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8008"))


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
            return _error_response(error)

    @app.get("/api/convert")
    def convert():
        try:
            return jsonify(
                service.convert(
                    request.args.get("from", "USD"),
                    request.args.get("to", "EUR"),
                    request.args.get("amount", "100"),
                )
            )
        except ServiceError as error:
            return _error_response(error)

    @app.get("/api/operations")
    def operations():
        try:
            return jsonify(
                {"operations": service.get_operations(request.args.get("limit", 50))}
            )
        except ServiceError as error:
            return _error_response(error)

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
            return _error_response(error)

    @app.get("/api/health")
    def health():
        cache_info = {}
        if hasattr(service, "cache") and hasattr(service.cache, "info"):
            cache_info = service.cache.info()
        return jsonify(
            {
                "status": "ok",
                "provider": getattr(service, "provider_name", "massive"),
                "cache": cache_info,
            }
        )

    return app


def _error_response(error):
    code = getattr(error, "code", "server_error")
    message = getattr(error, "message", str(error))
    status = getattr(error, "status", 500)
    return jsonify({"error": code, "message": message}), status


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    create_app().run(host=HOST, port=PORT, debug=debug)
