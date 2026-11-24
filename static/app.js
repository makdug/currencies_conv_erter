const I18N = {
  ru: {
    title: "Конвертер валют",
    subtitle: "Курсы, конвертация и история — локальный dashboard",
    converter: "Конвертер",
    chart: "График за 7 дней",
    rates: "Курсы валют",
    amount: "Сумма",
    from: "Из",
    to: "В",
    swap: "Поменять валюты местами",
    refresh: "Обновить данные",
    base: "Базовая валюта",
    search: "Поиск по коду или названию",
    favorites: "Избранное",
    code: "Код",
    currency: "Валюта",
    rate: "Курс",
    loading: "Загрузка...",
    online: "Онлайн",
    cache: "Данные из кэша",
    offline: "Офлайн",
    error: "Ошибка",
    updated: "Обновлено",
    asOf: "данные от",
    source: "Источник",
    daily: "дневное закрытие",
    intraday: "последняя сделка",
    reverse: "обратная пара",
    cross: "расчёт через USD",
    cached: "кэш",
    local: "локальный расчёт",
    notAvailable: "н/д",
    noResults: "Ничего не найдено",
    noFavorites: "В избранном пока пусто",
    tableLoading: "Загружаю курсы...",
    convertLoading: "Считаю...",
    chartLoading: "Загружаю историю...",
    chartTitle: "Курс",
    error_invalid_base: "Неизвестная базовая валюта",
    error_invalid_source: "Неизвестная валюта списания",
    error_invalid_target: "Неизвестная валюта зачисления",
    error_invalid_amount: "Сумма должна быть положительным числом",
    error_invalid_days: "Некорректный период истории",
    error_no_rate: "Для этой пары нет доступного курса",
    error_rates_unavailable: "Нет связи с API и нет сохранённых курсов",
    error_history_unavailable: "Не удалось получить историю",
    error_network: "Не удалось связаться с сервером",
    error_bad_request: "Некорректный запрос",
    error_unknown: "Неизвестная ошибка",
    footer: "Данные: Massive. Учебный проект, не инвестиционная рекомендация.",
  },
  en: {
    title: "Currency Converter",
    subtitle: "Rates, conversion and history — a local dashboard",
    converter: "Converter",
    chart: "7-day chart",
    rates: "Exchange rates",
    amount: "Amount",
    from: "From",
    to: "To",
    swap: "Swap currencies",
    refresh: "Refresh data",
    base: "Base currency",
    search: "Search by code or name",
    favorites: "Favorites",
    code: "Code",
    currency: "Currency",
    rate: "Rate",
    loading: "Loading...",
    online: "Online",
    cache: "Cached data",
    offline: "Offline",
    error: "Error",
    updated: "Updated",
    asOf: "data from",
    source: "Source",
    daily: "daily close",
    intraday: "last trade",
    reverse: "reverse pair",
    cross: "cross via USD",
    cached: "cache",
    local: "local calculation",
    notAvailable: "n/a",
    noResults: "Nothing found",
    noFavorites: "No favorites yet",
    tableLoading: "Loading rates...",
    convertLoading: "Converting...",
    chartLoading: "Loading history...",
    chartTitle: "Rate",
    error_invalid_base: "Unknown base currency",
    error_invalid_source: "Unknown source currency",
    error_invalid_target: "Unknown target currency",
    error_invalid_amount: "Amount must be a positive number",
    error_invalid_days: "Invalid history period",
    error_no_rate: "No rate available for this pair",
    error_rates_unavailable: "API is unavailable and no cached rates exist",
    error_history_unavailable: "Could not load history",
    error_network: "Could not reach the server",
    error_bad_request: "Bad request",
    error_unknown: "Unknown error",
    footer: "Data: Massive. Learning project, not investment advice.",
  },
};

const state = {
  currencies: [],
  byCode: {},
  lang: "ru",
  base: "USD",
  from: "USD",
  to: "EUR",
  amount: "100",
  search: "",
  favorites: [],
  favoritesOnly: false,
  rates: {},
  ratesMeta: null,
  convertMeta: null,
  convertError: null,
  historyMeta: null,
  historyError: null,
  updatedMeta: null,
  chart: null,
  chartPoints: [],
  statusKind: "loading",
  statusKey: "loading",
  errorKey: null,
  errorText: null,
  convertTimer: null,
};

const els = {};

function t(key) {
  return (I18N[state.lang] && I18N[state.lang][key]) || key;
}

function errorMessage(error) {
  const key = error && error.code ? `error_${error.code}` : "error_unknown";
  return I18N[state.lang][key] || (error && error.message) || t("error_unknown");
}

function formatNumber(value, minimum = 2, maximum = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "—";
  }
  return new Intl.NumberFormat(state.lang === "ru" ? "ru-RU" : "en-US", {
    minimumFractionDigits: minimum,
    maximumFractionDigits: maximum,
  }).format(number);
}

function formatRate(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "—";
  }
  const absolute = Math.abs(number);
  if (absolute >= 1000) {
    return formatNumber(number, 2, 2);
  }
  if (absolute >= 1) {
    return formatNumber(number, 2, 4);
  }
  if (absolute >= 0.01) {
    return formatNumber(number, 4, 6);
  }
  return formatNumber(number, 6, 8);
}

function formatTime(iso) {
  if (!iso) {
    return "";
  }
  const locale = state.lang === "ru" ? "ru-RU" : "en-US";
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    return new Intl.DateTimeFormat(locale, {
      dateStyle: "short",
      timeZone: "UTC",
    }).format(new Date(`${iso}T00:00:00Z`));
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  const formatted = new Intl.DateTimeFormat(locale, {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Europe/Moscow",
  }).format(date);
  return `${formatted} ${state.lang === "ru" ? "МСК" : "MSK"}`;
}

function currencyName(code) {
  const currency = state.byCode[code];
  if (!currency) {
    return code;
  }
  if (state.lang === "ru" && currency.name_ru) {
    return currency.name_ru;
  }
  return currency.name_en || code;
}

function currencyLabel(code) {
  return `${code} — ${currencyName(code)}`;
}

function escapeHtml(value) {
  const replacements = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };
  return String(value).replace(/[&<>"']/g, (character) => replacements[character]);
}

function sourceLabel(meta) {
  if (!meta) {
    return "";
  }
  const source = meta.source || "";
  if (source === "massive") {
    return t("daily");
  }
  if (source === "massive_intraday") {
    return t("intraday");
  }
  if (source === "massive_reverse") {
    return t("reverse");
  }
  if (source === "massive_cross") {
    return t("cross");
  }
  if (source === "cache") {
    return t("cached");
  }
  if (source === "local") {
    return t("local");
  }
  return source;
}

function noteText(meta) {
  if (!meta) {
    return "";
  }
  const time = meta.as_of ? formatTime(meta.as_of) : "";
  const suffix = time ? ` · ${t("asOf")} ${time}` : "";
  const label = meta.stale ? t("cached") : sourceLabel(meta);
  return `${t("source")}: ${label}${suffix}`;
}

function setStatus(kind, key) {
  state.statusKind = kind;
  state.statusKey = key;
  els.status.className = `status status-${kind}`;
  els.statusText.textContent = t(key);
}

function setUpdated(meta) {
  state.updatedMeta = meta || null;
  const time = meta && (meta.fetched_at || meta.as_of);
  els.updated.textContent = time
    ? `${t("updated")}: ${formatTime(time)}`
    : "";
}

function updateStatusFromMeta(meta) {
  if (!navigator.onLine) {
    setStatus("offline", "offline");
  } else if (meta && meta.stale) {
    setStatus("cache", "cache");
  } else {
    setStatus("online", "online");
  }
  setUpdated(meta);
}

function showError(message) {
  els.error.textContent = message;
  els.error.hidden = false;
}

function clearError() {
  state.errorKey = null;
  state.errorText = null;
  els.error.hidden = true;
  els.error.textContent = "";
}

function rememberError(error) {
  const key = error && error.code ? `error_${error.code}` : "error_unknown";
  state.errorKey = key;
  state.errorText = errorMessage(error);
  showError(I18N[state.lang][key] || state.errorText);
}

function handleError(error) {
  rememberError(error);
  if (!navigator.onLine) {
    setStatus("offline", "offline");
  } else {
    setStatus("error", "error");
  }
}

async function api(url) {
  let response;
  try {
    response = await fetch(url, { headers: { Accept: "application/json" } });
  } catch (cause) {
    const error = new Error(t("error_network"));
    error.code = "network";
    throw error;
  }
  let data = null;
  try {
    data = await response.json();
  } catch (cause) {
    data = null;
  }
  if (!response.ok) {
    const error = new Error(
      (data && data.message) || t("error_unknown"),
    );
    error.code = (data && data.error) || "unknown";
    error.status = response.status;
    throw error;
  }
  return data;
}

function updateTableNote(meta) {
  els.tableNote.textContent = meta ? noteText(meta) : "";
}

function updateConvertNote(meta) {
  els.convertNote.textContent = meta ? noteText(meta) : "";
}

function renderConvert(data) {
  if (!data) {
    els.result.textContent = "—";
    els.rate.textContent = "";
    updateConvertNote(null);
    return;
  }
  els.result.textContent = `${formatNumber(data.result, 2, 2)} ${data.to}`;
  els.rate.textContent = `1 ${data.from} = ${formatRate(data.rate)} ${data.to}`;
  updateConvertNote(data);
}

function updateChartNote(meta) {
  els.chartNote.textContent = meta ? noteText(meta) : "";
}

function renderTable() {
  if (!state.ratesMeta && !Object.keys(state.rates).length) {
    els.ratesBody.innerHTML = `<tr><td colspan="4" class="empty">${t("tableLoading")}</td></tr>`;
    els.tableNote.textContent = "";
    return;
  }

  const query = state.search.trim().toLowerCase();
  const rows = state.currencies.filter((currency) => {
    if (state.favoritesOnly && !state.favorites.includes(currency.code)) {
      return false;
    }
    if (!query) {
      return true;
    }
    const name = currencyName(currency.code).toLowerCase();
    return currency.code.toLowerCase().includes(query) || name.includes(query);
  });

  if (!rows.length) {
    const message = state.favoritesOnly ? t("noFavorites") : t("noResults");
    els.ratesBody.innerHTML = `<tr><td colspan="4" class="empty">${message}</td></tr>`;
    updateTableNote(state.ratesMeta);
    return;
  }

  els.ratesBody.innerHTML = rows.map((currency) => {
    const code = currency.code;
    const rate = state.rates[code];
    const isBase = code === state.base;
    const isFavorite = state.favorites.includes(code);
    const rateText = isBase
      ? formatNumber(1, 2, 2)
      : rate === undefined
        ? t("notAvailable")
        : formatRate(rate);
    return `<tr class="${isBase ? "base-row" : ""}">
      <td class="star-cell">
        <button type="button" class="star ${isFavorite ? "active" : ""}"
                data-code="${code}" title="${t("favorites")}">
          ${isFavorite ? "★" : "☆"}
        </button>
      </td>
      <td class="code">${code}</td>
      <td>${escapeHtml(currencyName(code))}</td>
      <td class="right">${rateText}</td>
    </tr>`;
  }).join("");

  els.ratesBody.querySelectorAll(".star").forEach((button) => {
    button.addEventListener("click", () => toggleFavorite(button.dataset.code));
  });
  updateTableNote(state.ratesMeta);
}

function toggleFavorite(code) {
  const index = state.favorites.indexOf(code);
  if (index === -1) {
    state.favorites.push(code);
  } else {
    state.favorites.splice(index, 1);
  }
  saveState();
  renderTable();
}

function renderAllSelects() {
  fillSelect(els.from, state.from);
  fillSelect(els.to, state.to);
  fillSelect(els.base, state.base);
}

function fillSelect(select, selected) {
  select.innerHTML = state.currencies.map((currency) => {
    const code = currency.code;
    return `<option value="${code}">${escapeHtml(currencyLabel(code))}</option>`;
  }).join("");
  select.value = selected;
}

function updateChart(points) {
  state.chartPoints = points || [];
  if (!state.chart) {
    return;
  }
  state.chart.data.labels = state.chartPoints.map((point) => point.date);
  state.chart.data.datasets[0].data = state.chartPoints.map(
    (point) => point.rate,
  );
  state.chart.options.scales.y.title.text = t("chartTitle");
  state.chart.update();
}

function initChart() {
  if (typeof Chart === "undefined") {
    return;
  }
  const context = els.chart.getContext("2d");
  state.chart = new Chart(context, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "",
          data: [],
          borderColor: "#2f6fed",
          backgroundColor: "rgba(47, 111, 237, 0.12)",
          borderWidth: 2,
          pointRadius: 2,
          pointHoverRadius: 4,
          tension: 0.25,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (context) =>
              `${formatRate(context.parsed.y)} ${state.to}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { maxTicksLimit: 7 },
        },
        y: {
          title: { display: true, text: t("chartTitle") },
          ticks: { callback: (value) => formatRate(value) },
        },
      },
    },
  });
}

async function loadRates(clear = false) {
  if (clear) {
    state.rates = {};
    state.ratesMeta = null;
    renderTable();
  }
  try {
    const data = await api(`/api/rates?base=${encodeURIComponent(state.base)}`);
    state.rates = data.rates || {};
    state.ratesMeta = data;
    renderTable();
    updateStatusFromMeta(data);
    clearError();
  } catch (error) {
    handleError(error);
    els.tableNote.textContent = errorMessage(error);
  }
}

async function convert() {
  const amount = Number(state.amount);
  if (!Number.isFinite(amount) || amount <= 0) {
    els.result.textContent = "—";
    els.rate.textContent = "";
    els.convertNote.textContent = t("error_invalid_amount");
    return;
  }
  els.result.textContent = t("convertLoading");
  els.rate.textContent = "";
  els.convertNote.textContent = "";
  try {
    const params = new URLSearchParams({
      from: state.from,
      to: state.to,
      amount: String(amount),
    });
    const data = await api(`/api/convert?${params.toString()}`);
    state.convertMeta = data;
    state.convertError = null;
    renderConvert(data);
    clearError();
  } catch (error) {
    state.convertMeta = null;
    state.convertError = error;
    els.result.textContent = "—";
    els.rate.textContent = "";
    els.convertNote.textContent = errorMessage(error);
    rememberError(error);
  }
}

async function loadHistory() {
  els.chartNote.textContent = t("chartLoading");
  try {
    const params = new URLSearchParams({
      from: state.from,
      to: state.to,
      days: "7",
    });
    const data = await api(`/api/history?${params.toString()}`);
    state.historyMeta = data;
    state.historyError = null;
    updateChart(data.points || []);
    updateChartNote(data);
    els.chartPair.textContent = `${data.from} → ${data.to}`;
    clearError();
  } catch (error) {
    state.historyMeta = null;
    state.historyError = error;
    updateChart([]);
    els.chartNote.textContent = errorMessage(error);
    els.chartPair.textContent = `${state.from} → ${state.to}`;
    rememberError(error);
  }
}

async function refreshAll() {
  await Promise.allSettled([loadRates(false), convert()]);
}

function setLanguage(lang) {
  state.lang = lang === "en" ? "en" : "ru";
  saveState();
  document.documentElement.lang = state.lang;
  document.title = t("title");
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((element) => {
    element.title = t(element.dataset.i18nTitle);
  });
  document.querySelectorAll(".lang-switch button").forEach((button) => {
    button.classList.toggle("active", button.dataset.lang === state.lang);
  });
  renderAllSelects();
  renderTable();
  updateChart(state.chartPoints);
  if (state.chart) {
    state.chart.options.scales.y.title.text = t("chartTitle");
    state.chart.update();
  }
  setStatus(state.statusKind, state.statusKey);
  setUpdated(state.updatedMeta);
  if (state.convertMeta) {
    renderConvert(state.convertMeta);
  } else if (state.convertError) {
    els.convertNote.textContent = errorMessage(state.convertError);
  }
  if (state.historyMeta) {
    updateChartNote(state.historyMeta);
  } else if (state.historyError) {
    els.chartNote.textContent = errorMessage(state.historyError);
  }
  if (state.errorKey) {
    showError(I18N[state.lang][state.errorKey] || state.errorText);
  }
}

function loadState() {
  const savedLang = localStorage.getItem("fx_lang");
  state.lang = savedLang === "en" ? "en" : "ru";
  const savedBase = localStorage.getItem("fx_base");
  state.base = state.byCode[savedBase] ? savedBase : "USD";
  const savedFrom = localStorage.getItem("fx_from");
  state.from = state.byCode[savedFrom] ? savedFrom : "USD";
  const savedTo = localStorage.getItem("fx_to");
  state.to = state.byCode[savedTo] ? savedTo : "EUR";
  state.amount = localStorage.getItem("fx_amount") || "100";
  state.search = localStorage.getItem("fx_search") || "";
  state.favoritesOnly = localStorage.getItem("fx_favorites_only") === "true";
  try {
    const parsed = JSON.parse(localStorage.getItem("fx_favorites") || "[]");
    state.favorites = Array.isArray(parsed)
      ? parsed.filter((code) => state.byCode[code])
      : [];
  } catch (error) {
    state.favorites = [];
  }
}

function saveState() {
  localStorage.setItem("fx_lang", state.lang);
  localStorage.setItem("fx_base", state.base);
  localStorage.setItem("fx_from", state.from);
  localStorage.setItem("fx_to", state.to);
  localStorage.setItem("fx_amount", state.amount);
  localStorage.setItem("fx_search", state.search);
  localStorage.setItem("fx_favorites_only", String(state.favoritesOnly));
  localStorage.setItem("fx_favorites", JSON.stringify(state.favorites));
}

function onAmountInput() {
  state.amount = els.amount.value;
  saveState();
  clearTimeout(state.convertTimer);
  state.convertTimer = setTimeout(convert, 350);
}

function onFromChange() {
  state.from = els.from.value;
  saveState();
  convert();
  loadHistory();
}

function onToChange() {
  state.to = els.to.value;
  saveState();
  convert();
  loadHistory();
}

function onBaseChange() {
  state.base = els.base.value;
  saveState();
  loadRates(true);
}

function onSwap() {
  const previous = state.from;
  state.from = state.to;
  state.to = previous;
  els.from.value = state.from;
  els.to.value = state.to;
  saveState();
  convert();
  loadHistory();
}

function onSearch() {
  state.search = els.search.value;
  saveState();
  renderTable();
}

function onFavoritesOnly() {
  state.favoritesOnly = els.favoritesOnly.checked;
  saveState();
  renderTable();
}

function onRefresh() {
  refreshAll();
  loadHistory();
}

function onOnline() {
  refreshAll();
  loadHistory();
}

function onOffline() {
  setStatus("offline", "offline");
}

function onVisibility() {
  if (!document.hidden) {
    refreshAll();
  }
}

function bindEvents() {
  els.amount.addEventListener("input", onAmountInput);
  els.from.addEventListener("change", onFromChange);
  els.to.addEventListener("change", onToChange);
  els.base.addEventListener("change", onBaseChange);
  els.swap.addEventListener("click", onSwap);
  els.search.addEventListener("input", onSearch);
  els.favoritesOnly.addEventListener("change", onFavoritesOnly);
  els.refresh.addEventListener("click", onRefresh);
  document.querySelectorAll(".lang-switch button").forEach((button) => {
    button.addEventListener("click", () => setLanguage(button.dataset.lang));
  });
  window.addEventListener("online", onOnline);
  window.addEventListener("offline", onOffline);
  document.addEventListener("visibilitychange", onVisibility);
}

function init() {
  els.status = document.getElementById("status");
  els.statusText = document.getElementById("status-text");
  els.updated = document.getElementById("updated");
  els.error = document.getElementById("error");
  els.amount = document.getElementById("amount");
  els.from = document.getElementById("from");
  els.to = document.getElementById("to");
  els.base = document.getElementById("base");
  els.swap = document.getElementById("swap");
  els.refresh = document.getElementById("refresh");
  els.search = document.getElementById("search");
  els.favoritesOnly = document.getElementById("favorites-only");
  els.result = document.getElementById("result");
  els.rate = document.getElementById("rate");
  els.convertNote = document.getElementById("convert-note");
  els.chart = document.getElementById("chart");
  els.chartPair = document.getElementById("chart-pair");
  els.chartNote = document.getElementById("chart-note");
  els.ratesBody = document.getElementById("rates-body");
  els.tableNote = document.getElementById("table-note");

  state.currencies = window.CURRENCIES || [];
  state.byCode = {};
  state.currencies.forEach((currency) => {
    state.byCode[currency.code] = currency;
  });

  loadState();
  els.amount.value = state.amount;
  els.search.value = state.search;
  els.favoritesOnly.checked = state.favoritesOnly;

  initChart();
  setLanguage(state.lang);
  bindEvents();
  refreshAll();
  loadHistory();
  setInterval(refreshAll, 60000);
  setInterval(loadHistory, 300000);
}

document.addEventListener("DOMContentLoaded", init);
