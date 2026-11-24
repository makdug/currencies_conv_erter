import math
from datetime import datetime, timedelta, timezone

from .catalog import CURRENCIES, CURRENCY_BY_CODE
from .provider import ProviderError


class ServiceError(Exception):
    def __init__(self, message, code="bad_request", status=400):
        super().__init__(message)
        self.message = message
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
        rates_ttl=300,
        intraday_ttl=60,
        history_ttl=300,
        now=utc_now,
    ):
        self.provider = provider
        self.cache = cache
        self.rates_ttl = rates_ttl
        self.intraday_ttl = intraday_ttl
        self.history_ttl = history_ttl
        self.now = now

    def get_currencies(self):
        return CURRENCIES

    def get_rates(self, base="USD"):
        base = base.upper()
        if base not in CURRENCY_BY_CODE:
            raise ServiceError("Неизвестная базовая валюта", "invalid_base")
        snapshot, stale = self._load_rates()
        rates = self._build_rates(snapshot["pairs"], base)
        return {
            "base": base,
            "rates": rates,
            "as_of": snapshot.get("as_of"),
            "fetched_at": snapshot.get("fetched_at"),
            "date": snapshot.get("date"),
            "stale": stale,
            "source": "massive" if not stale else "cache",
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
            return {
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

        snapshot, stale = self._load_rates()
        pair = f"{source}{target}"
        intraday, intraday_stale = self._load_intraday(pair)
        pairs = dict(snapshot["pairs"])
        if intraday:
            pairs[pair] = {"rate": intraday["rate"], "timestamp": None}
        rate, path = self._find_rate(pairs, source, target)
        if rate is None:
            raise ServiceError("Для этой пары нет курса", "no_rate", 404)
        used_intraday = intraday is not None
        return {
            "from": source,
            "to": target,
            "amount": amount,
            "rate": rate,
            "result": amount * rate,
            "path": path,
            "as_of": (
                intraday.get("as_of") if used_intraday else snapshot.get("as_of")
            ),
            "fetched_at": (
                intraday.get("fetched_at")
                if used_intraday
                else snapshot.get("fetched_at")
            ),
            "stale": stale or intraday_stale,
            "source": "massive_intraday" if used_intraday else "massive",
        }

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
            raise ServiceError(
                "Период должен быть от 1 до 31 дня", "invalid_days"
            )

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

        pair = f"{source}{target}"
        history, stale = self._load_history(pair, days)
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
            try:
                pairs = self.provider.fetch_grouped(day)
            except ProviderError as error:
                last_error = error
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
        try:
            row = self.provider.fetch_intraday(pair)
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
            }
            self.cache.save_pair(pair, data)
            return data, False
        except ProviderError:
            if cached:
                return cached, True
            return None, False

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
                "Не удалось получить историю по паре",
                "history_unavailable",
                503,
            ) from error

    def _fetch_history(self, pair, days):
        source, target = pair[:3], pair[3:6]
        try:
            points = self.provider.fetch_daily(pair, days)
            if points:
                return {
                    "points": points,
                    "as_of": points[-1]["date"],
                    "fetched_at": as_iso(self.now()),
                    "source_name": "massive",
                }
        except ProviderError:
            pass

        if "USD" not in (source, target):
            try:
                source_points = self.provider.fetch_daily(
                    f"{source}USD", days
                )
                target_points = self.provider.fetch_daily(
                    f"{target}USD", days
                )
                target_by_date = {
                    point["date"]: point["rate"] for point in target_points
                }
                points = [
                    {
                        "date": point["date"],
                        "rate": point["rate"] / target_by_date[point["date"]],
                    }
                    for point in source_points
                    if point["date"] in target_by_date
                ]
                if points:
                    return {
                        "points": points,
                        "as_of": points[-1]["date"],
                        "fetched_at": as_iso(self.now()),
                        "source_name": "massive_cross",
                    }
            except ProviderError:
                pass

        reverse = target + source
        try:
            points = self.provider.fetch_daily(reverse, days)
            if points:
                return {
                    "points": [
                        {"date": point["date"], "rate": 1 / point["rate"]}
                        for point in points
                    ],
                    "as_of": points[-1]["date"],
                    "fetched_at": as_iso(self.now()),
                    "source_name": "massive_reverse",
                }
        except ProviderError:
            pass

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
            for neighbor, rate in graph.get(current, {}).items():
                if neighbor in rates:
                    continue
                rates[neighbor] = rates[current] * rate
                queue.append(neighbor)
        return rates

    @staticmethod
    def _find_rate(pairs, source, target):
        if source == target:
            return 1.0, [source]
        graph = RateService._build_graph(pairs)
        queue = [(source, 1.0, [source])]
        seen = {source}
        while queue:
            current, rate, path = queue.pop(0)
            for neighbor, edge in graph.get(current, {}).items():
                if neighbor in seen:
                    continue
                next_rate = rate * edge
                next_path = path + [neighbor]
                if neighbor == target:
                    return next_rate, next_path
                seen.add(neighbor)
                queue.append((neighbor, next_rate, next_path))
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
