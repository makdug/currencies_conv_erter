"""Небольшой пример запуска логики без HTTP-сервера."""

from dotenv import load_dotenv

from currency.factory import create_service

load_dotenv()


def main():
    service = create_service()
    rates = service.get_rates("USD")
    print("База:", rates["base"], "источник:", rates["source"])
    print("USD -> EUR:", rates["rates"].get("EUR"))
    print("100 USD -> EUR:", service.convert("USD", "EUR", 100))
    history = service.get_history("USD", "EUR", 7)
    print("Точек истории:", len(history["points"]))
    print("Операций в журнале:", len(service.get_operations()))


if __name__ == "__main__":
    main()
