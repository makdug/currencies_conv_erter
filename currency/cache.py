import json
import os
import tempfile
import threading
from pathlib import Path

from pymongo import MongoClient


class JsonCache:
    """Локальный JSON-кэш: курсы, история и журнал операций."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.data = self._read()

    def _read(self):
        try:
            with self.path.open(encoding="utf-8") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self):
        """Пишем через временный файл, чтобы не оставить битый JSON."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            dir=self.path.parent,
            suffix=".tmp",
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(self.data, file, ensure_ascii=False, indent=2)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def get_rates(self):
        with self._lock:
            return self.data.get("rates")

    def save_rates(self, rates):
        with self._lock:
            self.data["rates"] = rates
            self._write()

    def get_pair(self, pair):
        with self._lock:
            return self.data.get("pairs", {}).get(pair)

    def save_pair(self, pair, data):
        with self._lock:
            self.data.setdefault("pairs", {})[pair] = data
            self._write()

    def get_history(self, pair):
        with self._lock:
            return self.data.get("history", {}).get(pair)

    def save_history(self, pair, data):
        with self._lock:
            self.data.setdefault("history", {})[pair] = data
            self._write()

    def add_operation(self, operation):
        with self._lock:
            self.data.setdefault("operations", []).append(operation)
            self._write()

    def get_operations(self, limit=50):
        with self._lock:
            operations = self.data.get("operations", [])
            return list(reversed(operations[-limit:]))

    def info(self):
        with self._lock:
            rates = self.data.get("rates") or {}
            operations = self.data.get("operations", [])
            return {
                "has_rates": bool(rates),
                "path": str(self.path),
                "backend": "json",
                "operations_count": len(operations),
            }


class MongoCache:
    """Хранилище в MongoDB с тем же интерфейсом, что и JsonCache."""

    def __init__(
        self,
        url="mongodb://localhost:27017",
        db_name="currency_converter",
        client=None,
    ):
        self.url = url
        self.db_name = db_name
        self.client = client or MongoClient(url)
        self.db = self.client[db_name]
        self._rates = self.db["rates"]
        self._pairs = self.db["pairs"]
        self._history = self.db["history"]
        self._operations = self.db["operations"]

    @staticmethod
    def _get(collection, key):
        document = collection.find_one({"_id": key})
        return document.get("data") if document else None

    @staticmethod
    def _set(collection, key, data):
        collection.replace_one(
            {"_id": key},
            {"_id": key, "data": data},
            upsert=True,
        )

    def get_rates(self):
        return self._get(self._rates, "rates")

    def save_rates(self, rates):
        self._set(self._rates, "rates", rates)

    def get_pair(self, pair):
        return self._get(self._pairs, pair)

    def save_pair(self, pair, data):
        self._set(self._pairs, pair, data)

    def get_history(self, pair):
        return self._get(self._history, pair)

    def save_history(self, pair, data):
        self._set(self._history, pair, data)

    def add_operation(self, operation):
        document = dict(operation)
        document["_id"] = document["id"]
        self._operations.insert_one(document)

    def get_operations(self, limit=50):
        cursor = (
            self._operations.find({}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(limit)
        )
        return list(cursor)

    def info(self):
        rates = self.get_rates()
        return {
            "has_rates": bool(rates),
            "path": self.url,
            "backend": "mongodb",
            "operations_count": self._operations.count_documents({}),
        }
