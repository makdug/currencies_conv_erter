from datetime import date, datetime, timedelta, timezone

import requests

MASSIVE_BASE_URL = "https://api.massive.com"


class ProviderError(Exception):
    """Ошибка внешнего API."""


class MassiveProvider:
    source_name = "massive"

    def __init__(self, api_key, base_url=MASSIVE_BASE_URL, timeout=20, session=None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def _get(self, path, params=None):
        query = dict(params or {})
        query["apiKey"] = self.api_key
        try:
            response = self.session.get(
                f"{self.base_url}{path}",
                params=query,
                timeout=self.timeout,
            )
        except requests.Timeout as error:
            raise ProviderError("timeout") from error
        except requests.RequestException as error:
            raise ProviderError("network") from error

        if response.status_code == 429:
            raise ProviderError("rate_limit")
        if response.status_code >= 400:
            raise ProviderError(f"http_{response.status_code}")

        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderError("bad_json") from error

        status = payload.get("status")
        if status == "ERROR":
            raise ProviderError(payload.get("error", "api_error"))
        if status == "NOT_AUTHORIZED":
            raise ProviderError("not_authorized")
        return payload

    def fetch_grouped(self, day):
        payload = self._get(
            f"/v2/aggs/grouped/locale/global/market/forex/{day}",
            {"adjusted": "true"},
        )
        pairs = {}
        for row in payload.get("results") or []:
            ticker = row.get("T", "")
            if not ticker.startswith("C:") or len(ticker) < 8:
                continue
            pair = ticker[2:8]
            base, quote = pair[:3], pair[3:6]
            if base in ("XAU", "XAG") or quote in ("XAU", "XAG"):
                continue
            close = row.get("c")
            if close is None:
                continue
            pairs[pair] = {
                "rate": float(close),
                "timestamp": row.get("t"),
            }
        return pairs

    def fetch_intraday(self, pair):
        today = date.today()
        start = today - timedelta(days=5)
        payload = self._get(
            f"/v2/aggs/ticker/C:{pair}/range/1/minute/{start}/{today}",
            {"adjusted": "true", "sort": "desc", "limit": 1},
        )
        rows = payload.get("results") or []
        if not rows:
            raise ProviderError("no_data")
        row = rows[0]
        return {
            "rate": float(row["c"]),
            "timestamp": row.get("t"),
        }

    def fetch_daily(self, pair, days=7):
        today = date.today()
        start = today - timedelta(days=days)
        payload = self._get(
            f"/v2/aggs/ticker/C:{pair}/range/1/day/{start}/{today}",
            {"adjusted": "true", "sort": "asc", "limit": days + 2},
        )
        points = []
        for row in payload.get("results") or []:
            close = row.get("c")
            timestamp = row.get("t")
            if close is None or timestamp is None:
                continue
            moment = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
            points.append(
                {
                    "date": moment.date().isoformat(),
                    "rate": float(close),
                }
            )
        return points
