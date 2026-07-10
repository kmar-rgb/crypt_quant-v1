from __future__ import annotations

import pandas as pd

from .models import StageResult


def detect_stage(daily: pd.DataFrame, weekly: pd.DataFrame) -> StageResult:
    if len(daily) < 200 or len(weekly) < 30:
        return StageResult("Insufficient data", 0, None, "Needs at least 200 daily bars.")

    last = daily.iloc[-1]
    recent_weekly = weekly.tail(30)
    recent_close = float(last["close"])
    ma_50 = float(last.get("ma_50", float("nan")))
    ma_150 = float(last.get("ma_150", float("nan")))
    ma_200 = float(last.get("ma_200", float("nan")))

    base_high = float(recent_weekly["high"].max())
    base_low = float(recent_weekly["low"].min())
    base_depth_pct = (base_high - base_low) / base_high * 100 if base_high else None

    ma_200_series = daily["ma_200"].dropna()
    ma_200_slope_up = len(ma_200_series) > 21 and ma_200_series.iloc[-1] > ma_200_series.iloc[-21]
    ma_50_slope_flat_or_up = daily["ma_50"].dropna().tail(10).diff().mean() >= -0.02
    near_long_ma = abs(recent_close - ma_200) / recent_close <= 0.12 if ma_200 else False
    constructive_base = base_depth_pct is not None and 8 <= len(recent_weekly) <= 40 and base_depth_pct <= 35

    if recent_close > ma_50 > ma_150 > ma_200 and ma_200_slope_up:
        near_high = recent_close >= float(last.get("high_52w", recent_close)) * 0.85
        confidence = 90 if near_high else 75
        return StageResult(
            "Stage 2 uptrend",
            confidence,
            base_depth_pct,
            "Price is above key moving averages and the 200-day average is rising.",
        )

    if constructive_base and near_long_ma and ma_50_slope_flat_or_up:
        return StageResult(
            "Stage 1 accumulation",
            70,
            base_depth_pct,
            "Price is basing near the long moving average with contained depth.",
        )

    if recent_close < ma_150 and recent_close < ma_200:
        return StageResult(
            "Stage 4 decline",
            75,
            base_depth_pct,
            "Price is below the long moving averages.",
        )

    return StageResult(
        "Stage 3 distribution / transition",
        55,
        base_depth_pct,
        "Trend is mixed around the key moving averages.",
    )
