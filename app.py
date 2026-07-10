from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

from crypto_quant.config import DEFAULT_SQLITE_PATH, load_app_settings, load_runtime_settings


st.set_page_config(page_title="Crypto Quant Research", page_icon="CQ", layout="wide")

DEFAULT_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "TON"]
KEYLESS_CMC_ROOT = "https://pro-api.coinmarketcap.com/public-api"
COINGECKO_ROOT = "https://api.coingecko.com/api/v3"
COINGECKO_IDS_BY_SYMBOL = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "TON": "the-open-network",
}


def main() -> None:
    settings = load_app_settings()
    runtime = load_runtime_settings()

    with st.sidebar:
        st.title("Crypto Quant")
        page = st.radio(
            "Page",
            ["Market Overview", "Quant Screener", "AI Analyst Report", "Settings"],
            label_visibility="collapsed",
        )
        st.divider()
        symbols = st.text_input("Live symbols", ",".join(DEFAULT_SYMBOLS))
        refresh_live = st.button("Refresh live market data", type="primary")
        st.caption("Research classification only. No trades are placed.")

    if page == "Market Overview":
        market_overview(settings, symbols, refresh_live)
    elif page == "Quant Screener":
        quant_screener(settings, symbols, refresh_live)
    elif page == "AI Analyst Report":
        analyst_report()
    else:
        settings_page(settings, runtime)


def market_overview(settings: Any, symbols_text: str, refresh_live: bool) -> None:
    st.title("Crypto Market Overview")
    st.caption("BUY means quantitative research classification, not an instruction to purchase.")

    rows, source_note = load_market_rows(settings, symbols_text, refresh_live)
    st.caption(source_note)
    scanned = len(rows)
    buy_count = int((rows["rating"] == "BUY").sum()) if not rows.empty and "rating" in rows else 0
    watch_count = int((rows["rating"] == "WATCH").sum()) if not rows.empty and "rating" in rows else 0
    avoid_count = int((rows["rating"] == "AVOID").sum()) if not rows.empty and "rating" in rows else scanned
    average_score = float(rows["display_score"].mean()) if not rows.empty and "display_score" in rows else 0.0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Cryptocurrencies scanned", scanned)
    col2.metric("BUY", buy_count)
    col3.metric("WATCH", watch_count)
    col4.metric("AVOID", avoid_count)
    col5.metric("Average score", f"{average_score:.1f}/5")

    if rows.empty:
        empty_state()
        return

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.subheader("Rating Distribution")
        st.bar_chart(rows["rating"].value_counts())
    with chart_col2:
        st.subheader("Data Quality")
        st.bar_chart(rows["data_quality_status"].value_counts())

    st.subheader("Highest Ranked Quotes")
    st.dataframe(
        rows.sort_values(["display_score", "market_cap"], ascending=[False, False]).head(10),
        use_container_width=True,
        hide_index=True,
    )


def quant_screener(settings: Any, symbols_text: str, refresh_live: bool) -> None:
    st.title("Crypto Quant Screener")
    rows, source_note = load_market_rows(settings, symbols_text, refresh_live)
    st.caption(source_note)
    if rows.empty:
        empty_state()
        return

    ratings = st.multiselect("Rating", sorted(rows["rating"].dropna().unique()), default=sorted(rows["rating"].dropna().unique()))
    stages = st.multiselect("Stage", sorted(rows["stage"].dropna().unique()), default=sorted(rows["stage"].dropna().unique()))
    min_market_cap = st.number_input("Minimum market cap", min_value=0.0, value=float(settings.filters.minimum_market_cap), step=1_000_000.0)
    min_volume = st.number_input("Minimum 24h volume", min_value=0.0, value=float(settings.filters.minimum_24h_volume), step=500_000.0)

    filtered = rows[
        rows["rating"].isin(ratings)
        & rows["stage"].isin(stages)
        & rows["market_cap"].fillna(0).ge(min_market_cap)
        & rows["volume_24h"].fillna(0).ge(min_volume)
    ]

    columns = [
        "rank",
        "name",
        "symbol",
        "price",
        "percent_change_24h",
        "percent_change_7d",
        "percent_change_30d",
        "percent_change_90d",
        "market_cap",
        "volume_24h",
        "volume_to_market_cap",
        "stage",
        "display_score",
        "rating",
        "data_quality_status",
        "market_data_source",
        "last_updated",
    ]
    st.dataframe(filtered[[column for column in columns if column in filtered]], use_container_width=True, hide_index=True)


def analyst_report() -> None:
    st.title("AI Analyst Report")
    st.info(
        "The AI agent layer is scaffolded but not active yet. Deterministic crypto indicators, scoring, "
        "and agent runs will populate this page in later phases."
    )
    st.subheader("Configured Agent Roles")
    st.write("Research Agent: project purpose, sector, catalysts, risks, tokenomics, and missing information.")
    st.write("Technical Analysis Agent: deterministic indicators, stage evidence, setup quality, invalidation, and confirmation.")
    st.write("Head Analyst Agent: final non-advisory synthesis, confidence, conflicts, and BUY / WATCH / AVOID rationale.")


def settings_page(settings: Any, runtime: Any) -> None:
    st.title("Crypto Settings")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Scan")
        st.write(f"Maximum coins: {settings.scan.max_coins}")
        st.write(f"Default currency: {settings.scan.default_currency}")
        st.write(f"Timezone: {settings.scan.timezone}")

        st.subheader("Filters")
        st.write(f"Minimum market cap: {_money(settings.filters.minimum_market_cap)}")
        st.write(f"Minimum 24h volume: {_money(settings.filters.minimum_24h_volume)}")
        st.write(f"Minimum history days: {settings.data.min_history_days}")

    with col2:
        st.subheader("Ratings")
        st.write(f"BUY threshold: {settings.scoring.buy_threshold:.1f}/5")
        st.write(f"WATCH threshold: {settings.scoring.watch_threshold:.1f}/5")
        st.write(f"Minimum risk-to-reward: {settings.scoring.minimum_risk_reward:.1f}")

        st.subheader("API Status")
        st.write("Keyless CoinMarketCap public API enabled")
        st.write("CoinGecko public market API fallback enabled")
        st.write("CoinMarketCap API key configured" if runtime.coinmarketcap_api_key else "CoinMarketCap API key not configured for keyed endpoints")
        st.write(f"Database URL: `{runtime.database_url}`")


def load_market_rows(settings: Any, symbols_text: str, refresh_live: bool) -> tuple[pd.DataFrame, str]:
    symbols = parse_symbols(symbols_text)
    attempted_live = False
    live_error: str | None = None

    if refresh_live or not _sqlite_path().exists():
        attempted_live = True
        live_rows, error, source = load_live_market_data(
            tuple(symbols),
            settings.scan.default_currency,
            settings.data.request_timeout_seconds,
            settings.data.max_retries,
        )
        if not live_rows.empty:
            return live_rows, source
        if error:
            live_error = error

    stored_rows = load_screener_rows(settings.scan.default_currency)
    if not stored_rows.empty:
        if live_error:
            st.warning(f"{live_error} Showing stored local data instead.")
        return stored_rows, "Source: stored local database"

    if not attempted_live:
        live_rows, error, source = load_live_market_data(
            tuple(symbols),
            settings.scan.default_currency,
            settings.data.request_timeout_seconds,
            settings.data.max_retries,
        )
        if not live_rows.empty:
            return live_rows, source
        live_error = error

    if live_error:
        st.warning(live_error)
    return empty_screener_frame(), "Source: no market data available yet"


@st.cache_data(ttl=120, show_spinner=False)
def load_live_market_data(
    symbols: tuple[str, ...],
    currency: str,
    timeout_seconds: int,
    max_retries: int,
) -> tuple[pd.DataFrame, str | None, str]:
    cmc_error: str | None = None
    try:
        envelope = fetch_keyless_simple_price(
            symbols=list(symbols),
            convert=currency,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    except RuntimeError as exc:
        cmc_error = public_api_error_message(str(exc))
    else:
        frame = simple_price_frame(envelope.get("data"), currency, source="CoinMarketCap keyless")
        if not frame.empty:
            return frame, None, "Source: CoinMarketCap keyless public API"

    try:
        frame = fetch_coingecko_markets_frame(
            symbols=list(symbols),
            currency=currency,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    except RuntimeError as exc:
        fallback_error = f"CoinGecko fallback failed: {exc}"
        return empty_screener_frame(), "; ".join(item for item in [cmc_error, fallback_error] if item), "Source: no market data available yet"
    if not frame.empty:
        if cmc_error:
            return frame, None, "Source: CoinGecko public market API fallback because CoinMarketCap is unavailable"
        return frame, None, "Source: CoinGecko public market API fallback"
    return empty_screener_frame(), cmc_error or "No live market rows returned.", "Source: no market data available yet"


def fetch_keyless_simple_price(
    *,
    symbols: list[str],
    convert: str,
    timeout_seconds: int,
    max_retries: int,
) -> dict[str, Any]:
    cleaned_symbols = ",".join(symbol.strip().upper() for symbol in symbols if symbol.strip())
    query = urlencode({"symbol": cleaned_symbols, "convert": convert.upper()})
    url = f"{KEYLESS_CMC_ROOT}/v1/simple/price?{query}"
    request = Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        },
    )

    for attempt in range(max_retries + 1):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            status = payload.get("status") if isinstance(payload, dict) else None
            if isinstance(status, dict) and status.get("error_code"):
                raise RuntimeError(str(status.get("error_message") or "CoinMarketCap returned an error."))
            if not isinstance(payload, dict):
                raise RuntimeError("CoinMarketCap returned an unexpected response.")
            return payload
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= max_retries:
                raise RuntimeError(f"HTTP {exc.code}") from exc
            time.sleep(min(2**attempt, 30))
        except (TimeoutError, URLError) as exc:
            if attempt >= max_retries:
                raise RuntimeError("request failed after retries") from exc
            time.sleep(min(2**attempt, 30))
    raise RuntimeError("request failed")


def fetch_coingecko_markets_frame(
    *,
    symbols: list[str],
    currency: str,
    timeout_seconds: int,
    max_retries: int,
) -> pd.DataFrame:
    ids = [COINGECKO_IDS_BY_SYMBOL[symbol] for symbol in symbols if symbol in COINGECKO_IDS_BY_SYMBOL]
    if not ids:
        return empty_screener_frame()
    query = urlencode(
        {
            "vs_currency": currency.lower(),
            "ids": ",".join(ids),
            "order": "market_cap_desc",
            "per_page": len(ids),
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h,7d,30d",
        }
    )
    request = Request(
        f"{COINGECKO_ROOT}/coins/markets?{query}",
        method="GET",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "crypt-quant-v1/0.1",
        },
    )
    for attempt in range(max_retries + 1):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, list):
                raise RuntimeError("CoinGecko returned an unexpected response.")
            return coingecko_markets_frame(payload)
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= max_retries:
                raise RuntimeError(f"HTTP {exc.code}") from exc
            time.sleep(min(2**attempt, 30))
        except (TimeoutError, URLError) as exc:
            if attempt >= max_retries:
                raise RuntimeError("request failed after retries") from exc
            time.sleep(min(2**attempt, 30))
    raise RuntimeError("request failed")


def simple_price_frame(data: Any, currency: str, source: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    items = data.items() if isinstance(data, dict) else enumerate(data if isinstance(data, list) else [])
    for index, payload in items:
        item = payload if isinstance(payload, dict) else {}
        quote = item.get("quote", {}).get(currency) if isinstance(item.get("quote"), dict) else None
        flat_quote = item.get(currency) if isinstance(item.get(currency), dict) else None
        price = _first_number(item.get("price"), quote.get("price") if quote else None, flat_quote.get("price") if flat_quote else None, item.get(currency))
        rows.append(
            {
                "rank": item.get("cmc_rank") or item.get("rank"),
                "name": item.get("name") or str(index).upper(),
                "symbol": item.get("symbol") or str(index).upper(),
                "price": price,
                "percent_change_24h": _first_number(item.get("percent_change_24h"), quote.get("percent_change_24h") if quote else None),
                "percent_change_7d": _first_number(item.get("percent_change_7d"), quote.get("percent_change_7d") if quote else None),
                "percent_change_30d": _first_number(item.get("percent_change_30d"), quote.get("percent_change_30d") if quote else None),
                "percent_change_90d": _first_number(item.get("percent_change_90d"), quote.get("percent_change_90d") if quote else None),
                "market_cap": _first_number(item.get("market_cap"), quote.get("market_cap") if quote else None),
                "volume_24h": _first_number(item.get("volume_24h"), quote.get("volume_24h") if quote else None),
                "volume_to_market_cap": None,
                "stage": "Insufficient data",
                "stage_confidence": 0.0,
                "raw_score": 0.0,
                "display_score": 0.0,
                "rating": "AVOID",
                "data_quality_status": "missing_history",
                "market_data_source": source,
                "last_updated": item.get("last_updated") or (quote.get("last_updated") if quote else None),
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["volume_to_market_cap"] = frame.apply(_volume_to_market_cap, axis=1)
    return frame if not frame.empty else empty_screener_frame()


def coingecko_markets_frame(data: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in data:
        rows.append(
            {
                "rank": item.get("market_cap_rank"),
                "name": item.get("name"),
                "symbol": str(item.get("symbol", "")).upper(),
                "price": _first_number(item.get("current_price")),
                "percent_change_24h": _first_number(item.get("price_change_percentage_24h")),
                "percent_change_7d": _first_number(item.get("price_change_percentage_7d_in_currency")),
                "percent_change_30d": _first_number(item.get("price_change_percentage_30d_in_currency")),
                "percent_change_90d": None,
                "market_cap": _first_number(item.get("market_cap")),
                "volume_24h": _first_number(item.get("total_volume")),
                "volume_to_market_cap": None,
                "stage": "Insufficient data",
                "stage_confidence": 0.0,
                "raw_score": 0.0,
                "display_score": 0.0,
                "rating": "AVOID",
                "data_quality_status": "fallback_price_only",
                "market_data_source": "CoinGecko fallback",
                "last_updated": item.get("last_updated"),
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["volume_to_market_cap"] = frame.apply(_volume_to_market_cap, axis=1)
    return frame if not frame.empty else empty_screener_frame()


def load_screener_rows(currency: str) -> pd.DataFrame:
    db_path = _sqlite_path()
    if db_path is None or not db_path.exists():
        return empty_screener_frame()

    try:
        with sqlite3.connect(db_path) as connection:
            frame = pd.read_sql_query(
                """
                SELECT
                    c.market_cap_rank AS rank,
                    c.name,
                    c.symbol,
                    q.price,
                    q.percent_change_24h,
                    q.percent_change_7d,
                    q.percent_change_30d,
                    q.percent_change_90d,
                    q.market_cap,
                    q.volume_24h,
                    q.volume_to_market_cap,
                    'Insufficient data' AS stage,
                    0.0 AS stage_confidence,
                    0.0 AS raw_score,
                    0.0 AS display_score,
                    'AVOID' AS rating,
                    'missing_history' AS data_quality_status,
                    q.last_updated
                FROM cryptocurrencies c
                JOIN market_quotes q ON q.cmc_id = c.cmc_id
                WHERE q.currency = ?
                ORDER BY c.market_cap_rank IS NULL, c.market_cap_rank
                """,
                connection,
                params=(currency,),
            )
    except sqlite3.Error:
        return empty_screener_frame()
    return frame


def empty_screener_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "rank",
            "name",
            "symbol",
            "price",
            "percent_change_24h",
            "percent_change_7d",
            "percent_change_30d",
            "percent_change_90d",
            "market_cap",
            "volume_24h",
            "volume_to_market_cap",
            "stage",
            "stage_confidence",
            "raw_score",
            "display_score",
            "rating",
            "data_quality_status",
            "market_data_source",
            "last_updated",
        ]
    )


def empty_state() -> None:
    st.warning("No stored crypto scan data is available yet.")
    st.write("Use `Refresh live market data` to retry the public market data providers.")


def public_api_error_message(message: str) -> str:
    if "system is busy" in message.lower():
        return "CoinMarketCap keyless public API is temporarily busy. Try Refresh live market data again shortly."
    return f"CoinMarketCap keyless request failed: {message}"


def parse_symbols(symbols_text: str) -> list[str]:
    symbols = [symbol.strip().upper() for symbol in symbols_text.split(",") if symbol.strip()]
    return symbols or DEFAULT_SYMBOLS


def _first_number(*values: Any) -> float | None:
    for value in values:
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _volume_to_market_cap(row: pd.Series) -> float | None:
    market_cap = row.get("market_cap")
    volume = row.get("volume_24h")
    if market_cap and volume:
        return float(volume) / float(market_cap)
    return None


def _sqlite_path() -> Path | None:
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("sqlite:///"):
        return Path(database_url.replace("sqlite:///", "", 1))
    if database_url and database_url.startswith("sqlite://"):
        return Path(database_url.replace("sqlite://", "", 1))
    return DEFAULT_SQLITE_PATH


def _money(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"${float(value):,.0f}"


if __name__ == "__main__":
    main()
