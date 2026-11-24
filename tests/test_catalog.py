from currency.catalog import CURRENCIES, CURRENCY_BY_CODE


def test_catalog_has_unique_codes():
    codes = [currency["code"] for currency in CURRENCIES]
    assert len(codes) == len(set(codes))


def test_catalog_has_required_fields():
    for currency in CURRENCIES:
        assert len(currency["code"]) == 3
        assert currency["name_en"]
        assert currency["name_ru"]


def test_catalog_lookup():
    assert CURRENCY_BY_CODE["USD"]["name_en"] == "United States dollar"
    assert CURRENCY_BY_CODE["EUR"]["name_ru"] == "Евро"
