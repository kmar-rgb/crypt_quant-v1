from __future__ import annotations

from datetime import date

import pandas as pd

from .models import Alert, CupHandleResult, StageResult
from .criteria_engine import CriteriaResult


def build_alerts(
    ticker: str,
    scan_date: date,
    daily: pd.DataFrame,
    stage: StageResult,
    cup_handle: CupHandleResult,
    near_pivot_pct: float = 5.0,
) -> list[Alert]:
    latest_close = float(daily.iloc[-1]["close"])
    alerts: list[Alert] = []

    if cup_handle.pivot:
        distance_pct = (cup_handle.pivot - latest_close) / cup_handle.pivot * 100
        if cup_handle.status == "Breakout":
            alerts.append(
                Alert(ticker, scan_date, "breakout", f"{ticker} broke above pivot {cup_handle.pivot:.2f}.", 1)
            )
        elif 0 <= distance_pct <= near_pivot_pct:
            alerts.append(
                Alert(
                    ticker,
                    scan_date,
                    "near_pivot",
                    f"{ticker} is {distance_pct:.1f}% below pivot {cup_handle.pivot:.2f}.",
                    2,
                )
            )

    if stage.stage == "Stage 2 uptrend" and cup_handle.status in {"Handle near pivot", "Breakout"}:
        alerts.append(
            Alert(ticker, scan_date, "stage_2_setup", f"{ticker} has Stage 2 structure with a valid setup.", 2)
        )

    return alerts


def build_criteria_alerts(
    ticker: str,
    scan_date: date,
    daily: pd.DataFrame,
    result: CriteriaResult,
) -> list[Alert]:
    latest = daily.iloc[-1]
    alerts: list[Alert] = []

    if result.breakout_status == "Near pivot":
        alerts.append(Alert(ticker, scan_date, "near_pivot", f"{ticker} is near pivot {result.pivot:.2f}.", 2))
    if result.classification == "Breakout Confirmed":
        alerts.append(Alert(ticker, scan_date, "breakout_confirmed", f"{ticker} confirmed a breakout.", 1))
    if result.classification == "Failed Breakout":
        alerts.append(Alert(ticker, scan_date, "failed_breakout", f"{ticker} fell back below its pivot.", 1))

    close = float(latest["close"])
    ma_50 = float(latest.get("ma_50", 0) or 0)
    if ma_50 and close < ma_50:
        alerts.append(Alert(ticker, scan_date, "moving_average_violation", f"{ticker} closed below the 50-day average.", 2))

    volume_ratio = result.details.get("volume_ratio")
    if isinstance(volume_ratio, float) and volume_ratio >= 1.8:
        alerts.append(Alert(ticker, scan_date, "volume_spike", f"{ticker} volume was {volume_ratio:.1f}x average.", 3))

    if result.details.get("rs_trending_higher"):
        alerts.append(Alert(ticker, scan_date, "relative_strength_improvement", f"{ticker} relative strength is improving.", 3))

    return alerts
