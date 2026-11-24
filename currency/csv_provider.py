import csv
from pathlib import Path

from .provider import ProviderError


class CsvRateProvider:
    """Провайдер курсов из локального CSV-файла.

    Формат файла: base,quote,rate. Такой источник можно использовать без
    интернета и без ключа Massive.
    """

    source_name = "csv"

    def __init__(self, path):
        self.path = Path(path)
        self.pairs = self._load()

    def _load(self):
        try:
            with self.path.open(encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)
                pairs = {}
                for row in reader:
                    base = (row.get("base") or "").strip().upper()
                    quote = (row.get("quote") or "").strip().upper()
                    rate = float(row.get("rate") or 0)
                    if not base or not quote or rate <= 0:
                        continue
                    pairs[f"{base}{quote}"] = {
                        "rate": rate,
                        "timestamp": None,
                    }
                return pairs
        except FileNotFoundError as error:
            raise ProviderError("csv_not_found") from error
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderError("csv_invalid") from error

    def _rate(self, pair):
        row = self.pairs.get(pair)
        if row:
            return row["rate"]

        base, quote = pair[:3], pair[3:6]
        reverse = self.pairs.get(f"{quote}{base}")
        if reverse:
            return 1 / reverse["rate"]

        if base != "USD" and quote != "USD":
            base_rate = self._rate(f"{base}USD")
            quote_rate = self._rate(f"{quote}USD")
            if base_rate is not None and quote_rate is not None:
                return base_rate / quote_rate
        return None

    def fetch_grouped(self, day=None):
        return self.pairs

    def fetch_intraday(self, pair):
        rate = self._rate(pair)
        if rate is None:
            raise ProviderError("no_data")
        return {"rate": rate, "timestamp": None}

    def fetch_daily(self, pair, days=7):
        rate = self._rate(pair)
        if rate is None:
            return []
        return [{"date": "csv", "rate": rate}]
