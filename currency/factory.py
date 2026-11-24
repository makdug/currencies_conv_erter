import os

from .cache import JsonCache, MongoCache
from .csv_provider import CsvRateProvider
from .provider import MassiveProvider
from .service import RateService


def create_storage():
    mongo_url = os.getenv("MONGO_URL")
    if mongo_url:
        return MongoCache(
            mongo_url,
            os.getenv("MONGO_DB", "currency_converter"),
        )
    return JsonCache(os.getenv("CACHE_PATH", "data/cache.json"))


def create_service():
    csv_path = os.getenv("CSV_RATES_PATH", "currency/rates.csv")
    csv_provider = CsvRateProvider(csv_path)
    api_key = os.getenv("MASSIVE_API_KEY")
    source = os.getenv("RATES_SOURCE", "auto").lower()

    if source == "csv" or not api_key:
        provider = csv_provider
        fallback = None
    else:
        provider = MassiveProvider(
            api_key,
            base_url=os.getenv(
                "MASSIVE_BASE_URL", "https://api.massive.com"
            ),
            timeout=int(os.getenv("REQUEST_TIMEOUT", "20")),
        )
        fallback = csv_provider

    return RateService(
        provider=provider,
        cache=create_storage(),
        fallback_provider=fallback,
        rates_ttl=int(os.getenv("RATES_TTL", "60")),
        intraday_ttl=int(os.getenv("INTRADAY_TTL", "60")),
        history_ttl=int(os.getenv("HISTORY_TTL", "300")),
    )
