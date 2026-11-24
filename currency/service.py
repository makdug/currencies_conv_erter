import math
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .catalog import CURRENCIES, CURRENCY_BY_CODE
from .provider import ProviderError


class ServiceError(Exception):
    def __init__(self, message, code="bad_request", status=400):
        super().__init__(message)
        self.code = code
        self.status = status


def utc_now():
    return datetime.now(timezone.utc)


def as_iso(value):
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class RateService:
    def __init__(
        self,
        provider,
        cache,
        fallback_provider=None,
        rates_ttl=300,
        intraday_ttl=60,
        history_ttl=300,
        now=utc_now,
    ):
        self.provider = provider
        self.cache = cache
        self.fallback_provider = fallback_provider
        self.rates_ttl = rates_ttl
        self.intraday_ttl = intraday_ttl
        self.history_ttl = history_ttl
        self.now = now

    @property
    def provider_name(self):
        return getattr(self.provider, "source_name", "massive")

    def get_currencies(self):
        return CURRENCIES

    def get_operations(self, limit=50):
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise ServiceError(
                "Лимит должен быть числом", "invalid_limit"
            ) from None
        if limit < 1 or limit > 500:
            raise ServiceError("Лимит должен быть от 1 до 500", "invalid_limit")
        return self.cache.get_operations(limit)

    def get_rates(self, base="USD"):
        base = base.upper()
        if base not in CURRENCY_BY_CODE:
            raise ServiceError("Неизвестная базовая валюта", "invalid_base")
        snapshot, stale = self._load_rates()
        return {
            "base": base,
            "rates": self._build_rates(snapshot["pairs"], base),
            "as_of": snapshot.get("as_of"),
            "fetched_at": snapshot.get("fetched_at"),
            "stale": stale,
            "source": "cache" if stale else snapshot.get("source_name", "massive"),
        }

    def convert(self, source, target, amount):
        source = source.upper()
        target = target.upper()
        if source not in CURRENCY_BY_CODE:
            raise ServiceError("Неизвестная валюта списания", "invalid_source")
        if target not in CURRENCY_BY_CODE:
            raise ServiceError("Неизвестная валюта зачисления", "invalid_target")
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise ServiceError(
                "Сумма должна быть числом", "invalid_amount"
            ) from None
        if not math.isfinite(amount) or amount <= 0:
            raise ServiceError(
                "Сумма должна быть больше нуля", "invalid_amount"
            )

        if source == target:
            moment = as_iso(self.now())
            result = {
                "from": source,
                "to": target,
                "amount": amount,
                "rate": 1.0,
                "result": amount,
                "path": [source],
                "as_of": moment,
                "fetched_at": moment,
                "stale": False,
                "source": "local",
            }
            return self._record_operation(result)

        snapshot, stale = self._load_rates()
        pair = source + target
        intraday, intraday_stale = self._load_intraday(pair)
        pairs = dict(snapshot["pairs"])
        if intraday:
            pairs[pair] = {"rate": intraday["rate"], "timestamp": None}
        rate, path = self._find_rate(pairs, source, target)
        if rate is None:
            raise ServiceError("Для этой пары нет курса", "no_rate", 404)
        used_intraday = intraday is not None
        if used_intraday:
            source_name = intraday.get("source_name", "massive")
            source_name = f"{source_name}_intraday"
        else:
            source_name = snapshot.get("source_name", "massive")
        result = {
            "from": source,
            "to": target,
            "amount": amount,
            "rate": rate,
            "result": amount * rate,
            "path": path,
            "as_of": (
                intraday.get("as_of")
                if used_intraday
                else snapshot.get("as_of")
            ),
            "fetched_at": (
                intraday.get("fetched_at")
                if used_intraday
                else snapshot.get("fetched_at")
            ),
            "stale": stale or intraday_stale,
            "source": source_name,
        }
        return self._record_operation(result)

    def get_history(self, source, target, days=7):
        source = source.upper()
        target = target.upper()
        if source not in CURRENCY_BY_CODE:
            raise ServiceError("Неизвестная валюта", "invalid_source")
        if target not in CURRENCY_BY_CODE:
            raise ServiceError("Неизвестная валюта", "invalid_target")
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise ServiceError(
                "Период должен быть числом", "invalid_days"
            ) from None
        if days < 1 or days > 31:
            raise ServiceError("Период должен быть от 1 до 31 дня", "invalid_days")

        if source == target:
            points = [
                {
                    "date": (
                        self.now().date() - timedelta(days=offset)
                    ).isoformat(),
                    "rate": 1.0,
                }
                for offset in range(days - 1, -1, -1)
            ]
            return {
                "from": source,
                "to": target,
                "days": days,
                "points": points,
                "as_of": points[-1]["date"],
                "fetched_at": as_iso(self.now()),
                "stale": False,
                "source": "local",
            }

        history, stale = self._load_history(source + target, days)
        return {
            "from": source,
            "to": target,
            "days": days,
            "points": history["points"],
            "as_of": history.get("as_of"),
            "fetched_at": history.get("fetched_at"),
            "stale": stale,
            "source": history.get("source_name", "massive"),
        }

    def _record_operation(self, result):
        operation = {
            "id": uuid4().hex,
            "timestamp": as_iso(self.now()),
            "from": result["from"],
            "to": result["to"],
            "amount": result["amount"],
            "rate": result["rate"],
            "result": result["result"],
            "source": result["source"],
            "stale": result["stale"],
        }
        self.cache.add_operation(operation)
        result["operation_id"] = operation["id"]
        return result

    def _load_rates(self):
        cached = self.cache.get_rates()
        if cached and self._fresh(cached.get("fetched_at"), self.rates_ttl):
            return cached, False
        try:
            snapshot = self._fetch_rates()
            return snapshot, False
        except ProviderError as error:
            if cached:
                return cached, True
            raise ServiceError(
                "Нет связи с API и нет сохранённых курсов",
                "rates_unavailable",
                503,
            ) from error

    def _fetch_rates(self):
        last_error = None
        for day in self._candidate_days():
            pairs = None
            source_name = "massive"
            try:
                pairs = self.provider.fetch_grouped(day)
                source_name = self.provider_name
            except ProviderError as error:
                last_error = error
                if self.fallback_provider is not None:
                    try:
                        pairs = self.fallback_provider.fetch_grouped(day)
                        source_name = getattr(
                            self.fallback_provider, "source_name", "csv"
                        )
                    except ProviderError as fallback_error:
                        last_error = fallback_error
                        pairs = None
                if pairs is None:
                    if str(error) in {
                        "rate_limit",
                        "network",
                        "not_authorized",
                        "http_401",
                    }:
                        break
                    continue
            if not pairs:
                continue
            timestamps = [
                item["timestamp"]
                for item in pairs.values()
                if item.get("timestamp")
            ]
            as_of = None
            if timestamps:
                as_of = as_iso(
                    datetime.fromtimestamp(
                        max(timestamps) / 1000, timezone.utc
                    )
                )
            snapshot = {
                "date": day.isoformat(),
                "as_of": as_of,
                "fetched_at": as_iso(self.now()),
                "source_name": source_name,
                "pairs": pairs,
            }
            self.cache.save_rates(snapshot)
            return snapshot
        if last_error:
            raise last_error
        raise ProviderError("no_data")

    def _candidate_days(self):
        day = self.now().date() - timedelta(days=1)
        found = 0
        while found < 3:
            if day.weekday() < 5:
                yield day
                found += 1
            day -= timedelta(days=1)

    def _load_intraday(self, pair):
        cached = self.cache.get_pair(pair)
        if cached and self._fresh(cached.get("fetched_at"), self.intraday_ttl):
            return cached, False
        row = None
        source_name = "massive"
        try:
            row = self.provider.fetch_intraday(pair)
            source_name = self.provider_name
        except ProviderError:
            if self.fallback_provider is not None:
                try:
                    row = self.fallback_provider.fetch_intraday(pair)
                    source_name = getattr(
                        self.fallback_provider, "source_name", "csv"
                    )
                except ProviderError:
                    row = None
        if row is None:
            return cached, cached is not None
        timestamp = row.get("timestamp")
        as_of = None
        if timestamp:
            as_of = as_iso(
                datetime.fromtimestamp(timestamp / 1000, timezone.utc)
            )
        data = {
            "rate": row["rate"],
            "as_of": as_of,
            "fetched_at": as_iso(self.now()),
            "source_name": source_name,
        }
        self.cache.save_pair(pair, data)
        return data, False

    def _load_history(self, pair, days):
        cache_key = f"{pair}:{days}"
        cached = self.cache.get_history(cache_key)
        if cached and self._fresh(cached.get("fetched_at"), self.history_ttl):
            return cached, False
        try:
            data = self._fetch_history(pair, days)
            self.cache.save_history(cache_key, data)
            return data, False
        except ProviderError as error:
            if cached:
                return cached, True
            raise ServiceError(
                "Нет истории по этой паре",
                "history_unavailable",
                503,
            ) from error

    def _daily_points(self, pair, days):
        try:
            points = self.provider.fetch_daily(pair, days)
            if points:
                return points, self.provider_name
        except ProviderError:
            pass
        if self.fallback_provider is not None:
            try:
                points = self.fallback_provider.fetch_daily(pair, days)
                if points:
                    return points, getattr(
                        self.fallback_provider, "source_name", "csv"
                    )
            except ProviderError:
                pass
        return [], None

    def _fetch_history(self, pair, days):
        source, target = pair[:3], pair[3:6]
        points, source_name = self._daily_points(pair, days)
        if points:
            return {
                "points": points,
                "as_of": points[-1]["date"],
                "fetched_at": as_iso(self.now()),
                "source_name": source_name,
            }

        if "USD" not in (source, target):
            source_points, source_name = self._daily_points(
                f"{source}USD", days
            )
            target_points, _ = self._daily_points(f"{target}USD", days)
            if source_points and target_points:
                target_by_date = {
                    point["date"]: point["rate"] for point in target_points
                }
                cross_points = [
                    {
                        "date": point["date"],
                        "rate": point["rate"] / target_by_date[point["date"]],
                    }
                    for point in source_points
                    if point["date"] in target_by_date
                ]
                if cross_points:
                    return {
                        "points": cross_points,
                        "as_of": cross_points[-1]["date"],
                        "fetched_at": as_iso(self.now()),
                        "source_name": f"{source_name}_cross",
                    }

        reverse = target + source
        points, source_name = self._daily_points(reverse, days)
        if points:
            return {
                "points": [
                    {"date": point["date"], "rate": 1 / point["rate"]}
                    for point in points
                ],
                "as_of": points[-1]["date"],
                "fetched_at": as_iso(self.now()),
                "source_name": f"{source_name}_reverse",
            }

        raise ProviderError("no_data")

    def _fresh(self, fetched_at, ttl):
        if not fetched_at:
            return False
        try:
            moment = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        return (self.now() - moment).total_seconds() < ttl

    @staticmethod
    def _build_rates(pairs, base):
        graph = RateService._build_graph(pairs)
        rates = {base: 1.0}
        queue = [base]
        while queue:
            current = queue.pop(0)
            for code, rate in graph.get(current, {}).items():
                if code in rates:
                    continue
                rates[code] = rates[current] * rate
                queue.append(code)
        return rates

    @staticmethod
    def _find_rate(pairs, source, target):
        graph = RateService._build_graph(pairs)
        queue = [(source, 1.0, [source])]
        visited = {source}
        while queue:
            current, rate, path = queue.pop(0)
            for code, edge in graph.get(current, {}).items():
                if code in visited:
                    continue
                next_rate = rate * edge
                next_path = path + [code]
                if code == target:
                    return next_rate, next_path
                visited.add(code)
                queue.append((code, next_rate, next_path))
        return None, None

    @staticmethod
    def _build_graph(pairs):
        graph = {}
        for pair, data in pairs.items():
            rate = data.get("rate")
            if not rate:
                continue
            base, quote = pair[:3], pair[3:6]
            graph.setdefault(base, {})[quote] = rate
            graph.setdefault(quote, {})[base] = 1 / rate
        return graph
