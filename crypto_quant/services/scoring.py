from __future__ import annotations

from crypto_quant.config import ScoringSettings
from crypto_quant.models import MarketStage, Rating, ScoreBreakdown


def calculate_weighted_score(breakdown: ScoreBreakdown, settings: ScoringSettings) -> tuple[float, float]:
    weights = [
        settings.stage_trend_weight,
        settings.breakout_structure_weight,
        settings.volume_liquidity_weight,
        settings.momentum_relative_strength_weight,
        settings.risk_entry_quality_weight,
    ]
    total_weight = sum(weights) or 5.0
    weighted = (
        breakdown.stage_trend * weights[0]
        + breakdown.breakout_structure * weights[1]
        + breakdown.volume_liquidity * weights[2]
        + breakdown.momentum_relative_strength * weights[3]
        + breakdown.risk_entry_quality * weights[4]
    )
    raw_score = weighted / total_weight * 5.0
    return raw_score, round(raw_score, 1)


def assign_rating(
    *,
    raw_score: float,
    stage: MarketStage,
    liquidity_passed: bool,
    risk_reward: float | None,
    excessive_extension: bool,
    critical_risk_flags: list[str],
    settings: ScoringSettings,
) -> Rating:
    if (
        raw_score < settings.watch_threshold
        or stage in {MarketStage.STAGE_3, MarketStage.STAGE_4, MarketStage.INSUFFICIENT_DATA}
        or not liquidity_passed
        or excessive_extension
        or critical_risk_flags
        or (risk_reward is not None and risk_reward < settings.minimum_risk_reward)
    ):
        return Rating.AVOID
    if (
        raw_score >= settings.buy_threshold
        and stage in {MarketStage.EARLY_STAGE_2, MarketStage.CONFIRMED_STAGE_2}
        and risk_reward is not None
        and risk_reward >= settings.minimum_risk_reward
    ):
        return Rating.BUY
    return Rating.WATCH
