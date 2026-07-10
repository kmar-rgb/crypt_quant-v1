from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from crypto_quant.cmc_client import CoinMarketCapError, CoinMarketCapPublicClient
from crypto_quant.config import DEFAULT_SQLITE_PATH, load_app_settings, load_runtime_settings


st.set_page_config(page_title="Crypto Quant Research", page_icon="CQ", layout="wide")

DEFAULT_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "TON"]


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

    st.subheader("Highest Ranked Stored Quotes")
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
        st.write("CoinMarketCap API key configured" if runtime.coinmarketcap_api_key else "CoinMarketCap API key not configured for keyed endpoints")
        st.write(f"Database URL: `{runtime.database_url}`")


def load_market_rows(settings: Any, symbols_text: str, refresh_live: bool) -> tuple[pd.DataFrame, str]:
    symbols = parse_symbols(symbols_text)
    if refresh_live or not _sqlite_path().exists():
        live_rows, error = load_keyless_simple_price(
            tuple(symbols),
            settings.scan.default_currency,
            settings.data.request_timeout_seconds,
            settings.data.max_retries,
        )
        if not live_rows.empty:
            return live_rows, "Source: CoinMarketCap keyless public API"
        if error:
            st.warning(error)

    stored_rows = load_screener_rows(settings.scan.default_currency)
    if not stored_rows.empty:
        return stored_rows, "Source: stored local database"

    live_rows, error = load_keyless_simple_price(
        tuple(symbols),
        settings.scan.default_currency,
        settings.data.request_timeout_seconds,
        settings.data.max_retries,
    )
    if error:
        st.warning(error)
    if not live_rows.empty:
        return live_rows, "Source: CoinMarketCap keyless public API"
    return empty_screener_frame(), "Source: no market data available yet"


@st.cache_data(ttl=120, show_spinner=False)
def load_keyless_simple_price(
    symbols: tuple[str, ...],
    currency: str,
    timeout_seconds: int,
    max_retries: int,
) -> tuple[pd.DataFrame, str | None]:
    client = CoinMarketCapPublicClient(
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )
    try:
        envelope = client.simple_price(symbols=list(symbols), convert=currency)
    except CoinMarketCapError as exc:
        return empty_screener_frame(), f"CoinMarketCap keyless request failed: {exc}"
    return simple_price_frame(envelope.data, currency), None


def simple_price_frame(data: Any, currency: str) -> pd.DataFrame:
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
                "last_updated": item.get("last_updated") or (quote.get("last_updated") if quote else None),
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
            "last_updated",
        ]
    )


def empty_state() -> None:
    st.warning("No stored crypto scan data is available yet.")
    st.write("Use `Refresh live market data` to call the CoinMarketCap keyless public API.")


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
