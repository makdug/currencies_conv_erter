"""Небольшой пример запуска сервиса без HTTP-сервера."""

from server import create_service


def main():
    service = create_service()
    rates = service.get_rates("USD")
    print("База:", rates["base"], "источник:", rates["source"])
    print("USD -> EUR:", rates["rates"].get("EUR"))
    print("100 USD -> EUR:", service.convert("USD", "EUR", 100))
    history = service.get_history("USD", "EUR", 7)
    print("Точек истории:", len(history["points"]))


if __name__ == "__main__":
    main()
