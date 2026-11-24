import json
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("currencies.json")


def load_currencies(path=CATALOG_PATH):
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


CURRENCIES = load_currencies()
CURRENCY_BY_CODE = {currency["code"]: currency for currency in CURRENCIES}
