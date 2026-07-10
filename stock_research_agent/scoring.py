from __future__ import annotations

import pandas as pd

from .models import CandidateScore, CupHandleResult, StageResult


def score_candidate(
    daily: pd.DataFrame,
    stage: StageResult,
    cup_handle: CupHandleResult,
) -> CandidateScore:
    latest = daily.iloc[-1]

    stage_score = {
        "Stage 2 uptrend": 25,
        "Stage 1 accumulation": 18,
        "Stage 3 distribution / transition": 8,
        "Stage 4 decline": 0,
    }.get(stage.stage, 0)

    cup_score = {
        "Breakout": 25,
        "Handle near pivot": 22,
        "Handle forming": 18,
        "Cup formed": 12,
        "Cup forming": 8,
    }.get(cup_handle.status, 0)

    volume_ratio = cup_handle.breakout_volume_ratio
    if volume_ratio is None:
        volume_ratio = _safe_ratio(latest.get("volume"), latest.get("volume_ma_50"))
    volume_score = min(20, max(0, (volume_ratio - 0.8) * 20)) if volume_ratio else 0

    rs_change = float(latest.get("rs_50d_change", 0) or 0)
    rs_score = min(15, max(0, 7.5 + rs_change / 2))

    trend_score = 0
    if latest.get("close", 0) > latest.get("ma_50", float("inf")):
        trend_score += 5
    if latest.get("ma_50", 0) > latest.get("ma_150", float("inf")):
        trend_score += 5
    if latest.get("ma_150", 0) > latest.get("ma_200", float("inf")):
        trend_score += 5

    total = round(stage_score + cup_score + volume_score + rs_score + trend_score, 1)
    notes = "; ".join([stage.notes, cup_handle.notes])
    return CandidateScore(
        total=total,
        stage=round(stage_score, 1),
        cup_handle=round(cup_score, 1),
        volume=round(volume_score, 1),
        relative_strength=round(rs_score, 1),
        trend=round(trend_score, 1),
        notes=notes,
    )


def _safe_ratio(numerator: object, denominator: object) -> float | None:
    try:
        numerator_float = float(numerator)
        denominator_float = float(denominator)
    except (TypeError, ValueError):
        return None
    if denominator_float <= 0:
        return None
    return numerator_float / denominator_float
