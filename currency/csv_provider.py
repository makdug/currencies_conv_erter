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

    def fetch_grouped(self, day=None):
        return self.pairs

    def fetch_intraday(self, pair):
        row = self.pairs.get(pair)
        if not row:
            raise ProviderError("no_data")
        return {"rate": row["rate"], "timestamp": None}

    def fetch_daily(self, pair, days=7):
        row = self.pairs.get(pair)
        if not row:
            return []
        return [{"date": "csv", "rate": row["rate"]}]
