import json
import os
import tempfile
import threading
from pathlib import Path


class JsonCache:
    """Минимальный локальный кэш: один JSON-файл рядом с проектом."""

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
        """Пишем во временный файл и заменяем им основной.

        Вызывается только под self._lock. Уникальное имя временного файла
        нужно, чтобы два одновременных запроса не мешали друг другу.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f"{self.path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(self.data, file, ensure_ascii=False, indent=2)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _get(self, key, default=None):
        with self._lock:
            return self.data.get(key, default)

    def _set(self, key, value):
        with self._lock:
            self.data[key] = value
            self._write()

    def get_rates(self):
        return self._get("rates")

    def save_rates(self, rates):
        self._set("rates", rates)

    def get_pair(self, pair):
        pairs = self._get("pairs", {})
        return pairs.get(pair)

    def save_pair(self, pair, data):
        with self._lock:
            pairs = self.data.setdefault("pairs", {})
            pairs[pair] = data
            self._write()

    def get_history(self, pair):
        history = self._get("history", {})
        return history.get(pair)

    def save_history(self, pair, data):
        with self._lock:
            history = self.data.setdefault("history", {})
            history[pair] = data
            self._write()

    def info(self):
        rates = self._get("rates") or {}
        return {
            "has_rates": bool(rates),
            "as_of": rates.get("as_of"),
            "fetched_at": rates.get("fetched_at"),
            "path": str(self.path),
        }


class MongoCache:
    """Заглушка на будущее: в планах заменить JSON на MongoDB."""

    def __init__(self, url):
        self.url = url
        raise NotImplementedError("MongoDB-кэш появится в следующих версиях")
