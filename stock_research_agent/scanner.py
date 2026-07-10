from __future__ import annotations

from datetime import date

import pandas as pd

from .alerts import build_criteria_alerts
from .config import ScanConfig
from .criteria_engine import evaluate_stock_criteria
from .data_provider import MarketDataProvider
from .indicators import add_moving_averages, add_relative_strength
from .models import Alert, Symbol
from .storage import create_scan_run, save_alerts, save_candidates, save_prices, upsert_symbols


def scan_symbols(
    symbols: list[Symbol],
    provider: MarketDataProvider,
    config: ScanConfig,
    start: str | date | None = None,
    end: str | date | None = None,
    persist: bool = True,
) -> tuple[pd.DataFrame, list[Alert]]:
    benchmark_raw = provider.fetch_daily(config.benchmark, start=start, end=end)
    if benchmark_raw.empty:
        raise RuntimeError(f"No benchmark data returned for {config.benchmark}.")
    benchmark = add_moving_averages(benchmark_raw)
    if persist:
        save_prices(config.benchmark, benchmark_raw)

    candidates: list[dict] = []
    all_alerts: list[Alert] = []
    scan_date = pd.Timestamp.utcnow().date()

    for symbol in symbols:
        raw = provider.fetch_daily(symbol.ticker, start=start, end=end)
        if len(raw) < config.min_history_days:
            continue

        daily = add_relative_strength(add_moving_averages(raw), benchmark)
        criteria = evaluate_stock_criteria(
            daily,
            benchmark,
            breakout_volume_ratio=config.breakout_volume_ratio,
        )
        latest = daily.iloc[-1]
        pivot = criteria.pivot
        distance_to_pivot_pct = None
        if pivot:
            distance_to_pivot_pct = round((pivot - float(latest["close"])) / pivot * 100, 2)
        suggested_stop = _suggested_stop(float(latest["close"]), pivot)
        risk_reward = _risk_reward_estimate(float(latest["close"]), pivot, suggested_stop)

        row = {
            "ticker": symbol.ticker,
            "market": symbol.market,
            "sector": symbol.sector,
            "score": criteria.scores.total,
            "classification": criteria.classification,
            "stage": criteria.stage,
            "stage_confidence": round(criteria.scores.stage_2_transition / 25 * 100, 1),
            "cup_handle_status": criteria.cup_handle_status,
            "pivot": pivot,
            "distance_to_pivot_pct": distance_to_pivot_pct,
            "volume_ratio": criteria.details.get("volume_ratio"),
            "rs_50d_change": criteria.details.get("rs_50d_change") or latest.get("rs_50d_change"),
            "base_depth_pct": criteria.details.get("base_depth_pct"),
            "market_condition_score": criteria.scores.market_condition,
            "risk_reward_score": criteria.scores.risk_reward,
            "suggested_stop_loss": suggested_stop,
            "risk_reward_estimate": risk_reward,
            "notes": " ".join(criteria.notes),
            "last_close": float(latest["close"]),
            "current_price": float(latest["close"]),
            "volume": float(latest["volume"]),
        }
        candidates.append(row)
        all_alerts.extend(build_criteria_alerts(symbol.ticker, scan_date, daily, criteria))

        if persist:
            save_prices(symbol.ticker, raw)

    result = pd.DataFrame(candidates).sort_values("score", ascending=False) if candidates else pd.DataFrame()

    if persist:
        upsert_symbols(symbols)
        scan_id = create_scan_run(config.market, config.benchmark)
        save_candidates(scan_id, candidates)
        save_alerts(scan_id, all_alerts)

    return result, all_alerts


def _suggested_stop(close: float, pivot: float | None) -> float | None:
    if not pivot:
        return None
    return round(min(close * 0.93, pivot * 0.92), 2)


def _risk_reward_estimate(close: float, pivot: float | None, stop: float | None) -> float | None:
    if not pivot or not stop or close <= stop:
        return None
    target = pivot + (pivot - stop) * 2
    return round((target - close) / (close - stop), 2)
