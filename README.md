# Конвертер валют

Учебный dashboard на Flask: конвертер валют по актуальному курсу, таблица всех
поддерживаемых валют, график за 7 дней и журнал операций.

## Что умеет

- Конвертирует сумму из одной валюты в другую.
- Кнопка **⇄** меняет валюты «Из» и «В» местами.
- Показывает таблицу всех валют, которые отдаёт API (127 фиатных валют).
- Строит график выбранной пары за 7 дней.
- Запоминает избранные валюты в браузере.
- Обновляет данные автоматически раз в 60 секунд.
- Сохраняет историю конвертаций и отдаёт её через `/api/operations`.
- Умеет работать с Massive API, локальным CSV-файлом и MongoDB.

## Источник курсов

Основной источник — [Massive](https://massive.com/). Это не биржа, а поставщик
рыночных данных: он агрегирует котировки банков, брокеров и маркет-мейкеров.
Конкретные банки в открытом доступе не перечисляются.

- Один запрос `grouped` отдаёт сразу все валютные пары за торговый день.
- Для выбранной пары дополнительно запрашивается последняя минутная свеча.
- Курсы между «непрямыми» парами считаются через граф валют: например,
  `RUB → USD → EUR`.
- Ключ хранится в `.env` в переменной `MASSIVE_API_KEY`.

Если ключа нет или `RATES_SOURCE=csv`, сервер читает курсы из
`currency/rates.csv`. Если Massive недоступен, CSV используется как резервный
источник. Формат файла: `base,quote,rate`.

Бесплатный тариф Massive ограничивает частоту запросов (около 5 в минуту),
поэтому в проекте есть TTL-кэш. TTL (time to live) — время жизни кэша: пока
оно не истекло, данные берутся из локального хранилища, а не из API.

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# MASSIVE_API_KEY можно оставить пустым: тогда данные возьмутся из CSV

python server.py
```

Откройте <http://localhost:8008>.

### Docker

```bash
cp .env.example .env
# при необходимости вставьте ключ MASSIVE_API_KEY
docker compose up --build
```

В `docker-compose.yml` поднимаются приложение и MongoDB. Если MongoDB не нужна,
уберите `MONGO_URL` из окружения приложения.

### Логика без HTTP

`main.py` показывает работу классов без серверной обвязки:

```bash
RATES_SOURCE=csv python main.py
```

В PyCharm этот файл можно запустить через **Run** или **Debug**. Точки останова
удобно ставить в `currency/service.py` и `currency/csv_provider.py`.

## MongoDB

По умолчанию данные хранятся в JSON-файле. Чтобы включить MongoDB, задайте:

```bash
MONGO_URL=mongodb://localhost:27017
MONGO_DB=currency_converter
```

В тестах MongoDB подменяется через `mongomock`, поэтому настоящая база для
прогона тестов не нужна.

## Переменные окружения

| Переменная | По умолчанию | Зачем нужна |
| --- | --- | --- |
| `MASSIVE_API_KEY` | — | Ключ Massive API. Необязателен. |
| `RATES_SOURCE` | `auto` | `auto`, `massive` или `csv`. |
| `CSV_RATES_PATH` | `currency/rates.csv` | Локальный CSV с курсами. |
| `HOST` | `127.0.0.1` | Адрес сервера. |
| `PORT` | `8008` | Порт сервера. |
| `CACHE_PATH` | `data/cache.json` | JSON-хранилище, если MongoDB выключена. |
| `MONGO_URL` | — | Строка подключения к MongoDB. |
| `MONGO_DB` | `currency_converter` | Имя базы MongoDB. |
| `RATES_TTL` | `60` | Сколько секунд считать снимок курсов свежим. |
| `INTRADAY_TTL` | `60` | TTL последней минутной свечи. |
| `HISTORY_TTL` | `300` | TTL истории для графика. |
| `FLASK_DEBUG` | `0` | `1` включает режим отладки Flask. |

## API

| Метод | Адрес | Что делает |
| --- | --- | --- |
| `GET` | `/` | Dashboard. |
| `GET` | `/api/currencies` | Список валют. |
| `GET` | `/api/rates?base=USD` | Курсы всех валют к базовой. |
| `GET` | `/api/convert?from=USD&to=EUR&amount=100` | Конвертация. |
| `GET` | `/api/history?from=USD&to=EUR&days=7` | История пары. |
| `GET` | `/api/operations?limit=50` | Журнал конвертаций. |
| `GET` | `/api/health` | Состояние сервиса и хранилища. |

Примеры запросов:

```bash
curl "http://localhost:8008/api/convert?from=USD&to=EUR&amount=100"
curl "http://localhost:8008/api/operations?limit=10"
curl "http://localhost:8008/api/health"
```

Пример ответа `/api/convert`:

```json
{
  "from": "USD",
  "to": "EUR",
  "amount": 100.0,
  "rate": 0.91675,
  "result": 91.675,
  "path": ["USD", "EUR"],
  "as_of": null,
  "fetched_at": "2026-11-24T12:33:04.296697Z",
  "stale": false,
  "source": "csv_intraday",
  "operation_id": "8a9cce4a8ebb48c6a611bd4b9e5b5c04"
}
```

Пример ответа `/api/operations`:

```json
{
  "operations": [
    {
      "id": "8a9cce4a8ebb48c6a611bd4b9e5b5c04",
      "timestamp": "2026-11-24T12:33:04.297246Z",
      "from": "USD",
      "to": "EUR",
      "amount": 100.0,
      "rate": 0.91675,
      "result": 91.675,
      "source": "csv_intraday",
      "stale": false
    }
  ]
}
```

Готовая коллекция Postman лежит в
`postman/currency-converter.postman_collection.json`.

## Результаты и тестирование

- 6 API-эндпоинтов и dashboard.
- 105 автотестов.
- 100% покрытия логики по бранчам.
- Проверяются конвертация, журнал операций, CSV-источник, негативные сценарии,
  MongoDB через `mongomock` и HTTP-запросы к `http://localhost:8008`.
- CI запускает `flake8` и `pytest --cov`.

## Проверки

```bash
pytest --cov
flake8 .
```

`pytest` проверяет логику, API, CSV-провайдер, JSON- и MongoDB-хранилища.
Тесты Massive не ходят в настоящий API: провайдер подменяется фейком.
`flake8` проверяет соблюдение PEP 8.

Хук `hooks/pre-commit` запускает те же проверки перед коммитом. Чтобы включить
его:

```bash
git config core.hooksPath hooks
```

## Планы

- [ ] Добавить service worker и PWA, чтобы dashboard открывался без сети.
- [ ] Обновлять `currency/rates.csv` по расписанию.
- [ ] Добавить криптовалюты и металлы.
- [ ] Сделать личные списки валют и настройки пользователя.

## Структура проекта

```text
currency/
  cache.py          # JSON-кэш и MongoDB-хранилище
  catalog.py        # загрузка списка валют
  csv_provider.py   # провайдер курсов из CSV
  currencies.json   # 127 валют: код, название, символ
  factory.py        # сборка сервиса по переменным окружения
  rates.csv         # локальные курсы на случай отсутствия API
  provider.py       # запросы к Massive API
  service.py        # конвертация, курсы, история, журнал операций
templates/
  index.html        # dashboard
static/
  app.js            # логика интерфейса
  styles.css        # стили
  vendor/           # Chart.js
tests/              # pytest, coverage и requests-тесты
hooks/
  pre-commit        # flake8 + pytest --cov
server.py           # Flask-приложение и API
main.py             # пример запуска без HTTP
```

## Ограничения

- Данные Massive — не тиковый поток, а последняя доступная свеча.
- В выходные и праздники используется последний торговый день.
- Бесплатный тариф Massive не подходит для высокой нагрузки.
- CSV-файл статический: его нужно обновлять отдельно.
- Проект учебный и не является инвестиционной рекомендацией.
