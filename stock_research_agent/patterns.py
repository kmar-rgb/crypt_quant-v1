from __future__ import annotations

import pandas as pd

from .models import CupHandleResult


def detect_cup_handle(daily: pd.DataFrame, breakout_volume_ratio: float = 1.4) -> CupHandleResult:
    if len(daily) < 120:
        return CupHandleResult("Insufficient data", None, None, None, None, None, "Needs at least 120 bars.")

    frame = daily.sort_values("date").tail(325).reset_index(drop=True)
    close = frame["close"]
    high = frame["high"]
    low = frame["low"]

    left_window = frame.iloc[:-30]
    if len(left_window) < 60:
        return CupHandleResult("Insufficient data", None, None, None, None, None, "Needs more history before handle.")

    left_idx = int(left_window["high"].idxmax())
    cup_low_idx = int(frame.loc[left_idx:, "low"].idxmin())
    if cup_low_idx <= left_idx:
        return CupHandleResult("No cup", None, None, None, None, None, "No decline after the left peak.")

    left_high = float(high.iloc[left_idx])
    cup_low = float(low.iloc[cup_low_idx])
    depth_pct = (left_high - cup_low) / left_high * 100
    valid_depth = 12 <= depth_pct <= 40

    best_setup = None
    for handle_days in range(5, 31):
        handle_start = len(frame) - handle_days
        if handle_start <= cup_low_idx + 10:
            continue

        right_zone = frame.loc[cup_low_idx : handle_start - 1]
        right_idx = int(right_zone["high"].idxmax())
        right_high = float(high.iloc[right_idx])
        duration_days = right_idx - left_idx
        recovered = right_high >= left_high * 0.85
        valid_duration = 35 <= duration_days <= 325
        if not (valid_depth and valid_duration and recovered):
            continue

        handle = frame.loc[handle_start:]
        handle_high = float(handle["high"].max())
        handle_low = float(handle["low"].min())
        handle_depth_pct = (handle_high - handle_low) / handle_high * 100 if handle_high else None
        valid_handle = (
            handle_depth_pct is not None
            and handle_depth_pct <= 15
            and float(handle["close"].iloc[-1]) >= handle_low * 1.03
        )
        if valid_handle:
            best_setup = (min(left_high, right_high), duration_days, handle_depth_pct)
            break

    if best_setup is None:
        right = frame.loc[cup_low_idx:]
        right_idx = int(right["high"].idxmax())
        if right_idx <= cup_low_idx:
            return CupHandleResult("No cup", None, None, None, None, None, "No right-side recovery.")
        right_high = float(high.iloc[right_idx])
        pivot = min(left_high, right_high)
        duration_days = right_idx - left_idx
        recovered = right_high >= left_high * 0.85
        valid_duration = 35 <= duration_days <= 325
        if valid_depth and valid_duration and recovered:
            return CupHandleResult("Cup formed", pivot, depth_pct, duration_days, None, None, "Cup is visible, but handle quality is not confirmed.")
        return CupHandleResult(
            "No cup",
            pivot,
            depth_pct,
            duration_days,
            None,
            None,
            "Cup shape does not meet depth, duration, or recovery rules.",
        )

    pivot, duration_days, handle_depth_pct = best_setup

    latest = frame.iloc[-1]
    volume_ma_50 = float(latest.get("volume_ma_50", 0) or 0)
    current_volume = float(latest["volume"])
    volume_ratio = current_volume / volume_ma_50 if volume_ma_50 else None
    breakout = float(latest["close"]) > pivot and volume_ratio is not None and volume_ratio >= breakout_volume_ratio

    if breakout:
        status = "Breakout"
        notes = "Price closed above pivot with confirming volume."
    elif float(latest["close"]) >= pivot * 0.95:
        status = "Handle near pivot"
        notes = "Handle is valid and price is within 5 percent of pivot."
    else:
        status = "Handle forming"
        notes = "Cup is valid and handle remains controlled."

    return CupHandleResult(status, pivot, depth_pct, duration_days, handle_depth_pct, volume_ratio, notes)
