from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .indicators import add_moving_averages


CLASS_IGNORE = "Ignore"
CLASS_EARLY_WATCH = "Early Watch"
CLASS_STRONG_WATCH = "Strong Watch"
CLASS_BREAKOUT_CANDIDATE = "Breakout Candidate"
CLASS_BREAKOUT_CONFIRMED = "Breakout Confirmed"
CLASS_EXTENDED = "Extended / Too Late"
CLASS_FAILED_BREAKOUT = "Failed Breakout"


@dataclass(frozen=True)
class CriteriaScores:
    stage_2_transition: float
    cup_handle_quality: float
    volume_confirmation: float
    relative_strength: float
    risk_reward: float
    market_condition: float

    @property
    def total(self) -> float:
        return round(
            self.stage_2_transition
            + self.cup_handle_quality
            + self.volume_confirmation
            + self.relative_strength
            + self.risk_reward
            + self.market_condition,
            1,
        )


@dataclass(frozen=True)
class CriteriaResult:
    classification: str
    stage: str
    cup_handle_status: str
    breakout_status: str
    scores: CriteriaScores
    pivot: float | None
    distance_to_pivot_pct: float | None
    extended_from_50d_pct: float | None
    details: dict[str, bool | float | str | None] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


def evaluate_stock_criteria(
    daily: pd.DataFrame,
    benchmark_daily: pd.DataFrame | None = None,
    *,
    breakout_volume_ratio: float = 1.4,
    max_extension_from_50d_pct: float = 12.0,
) -> CriteriaResult:
    """Evaluate swing-trading setup criteria and classify the stock.

    The input should contain daily OHLCV rows. Relative-strength columns are used
    when present; otherwise benchmark data is used when supplied.
    """

    if len(daily) < 150:
        scores = CriteriaScores(0, 0, 0, 0, 0, _score_market_condition(benchmark_daily)[0])
        return CriteriaResult(
            CLASS_IGNORE,
            "Insufficient data",
            "Insufficient data",
            "No breakout",
            scores,
            None,
            None,
            None,
            notes=("Needs at least 150 daily bars.",),
        )

    frame = _prepare_daily(daily)
    latest = frame.iloc[-1]
    base = _base_metrics(frame)
    cup = _cup_handle_metrics(frame)
    market_score, market_downtrend = _score_market_condition(benchmark_daily)
    stage, stage_score, stage_details = _score_stage_transition(frame, base, cup, market_downtrend)
    cup_score, cup_status, cup_details = _score_cup_handle(cup)
    volume_score, volume_details = _score_volume(frame, base, cup, breakout_volume_ratio)
    rs_score, rs_details = _score_relative_strength(frame, benchmark_daily)
    risk_score, risk_details = _score_risk_reward(frame, cup, max_extension_from_50d_pct)

    scores = CriteriaScores(stage_score, cup_score, volume_score, rs_score, risk_score, market_score)
    pivot = cup.get("pivot")
    latest_close = float(latest["close"])
    distance_to_pivot_pct = _pct_distance_to_pivot(latest_close, pivot)
    ma_50 = _safe_float(latest.get("ma_50"))
    extended_from_50d_pct = ((latest_close - ma_50) / ma_50 * 100) if ma_50 else None
    breakout_status = _breakout_status(frame, cup, breakout_volume_ratio, market_downtrend, max_extension_from_50d_pct)
    classification = _classify(scores, stage, cup_status, breakout_status, extended_from_50d_pct)

    details = {
        **stage_details,
        **cup_details,
        **volume_details,
        **rs_details,
        **risk_details,
        "market_strong_downtrend": market_downtrend,
    }
    notes = _build_notes(classification, stage, cup_status, breakout_status, scores)

    return CriteriaResult(
        classification=classification,
        stage=stage,
        cup_handle_status=cup_status,
        breakout_status=breakout_status,
        scores=scores,
        pivot=pivot,
        distance_to_pivot_pct=distance_to_pivot_pct,
        extended_from_50d_pct=extended_from_50d_pct,
        details=details,
        notes=notes,
    )


def _prepare_daily(daily: pd.DataFrame) -> pd.DataFrame:
    frame = daily.sort_values("date").reset_index(drop=True).copy()
    for column in ["ma_10", "ma_20", "ma_50", "ma_150", "ma_200", "volume_ma_20", "volume_ma_50"]:
        if column not in frame.columns:
            frame = add_moving_averages(frame)
            break
    frame["range_pct"] = (frame["high"] - frame["low"]) / frame["close"] * 100
    return frame


def _base_metrics(frame: pd.DataFrame) -> dict[str, float | bool]:
    base = frame.tail(65)
    prior = frame.iloc[-130:-65] if len(frame) >= 130 else frame.head(0)
    high = float(base["high"].max())
    low = float(base["low"].min())
    depth_pct = (high - low) / high * 100 if high else 0
    net_change_pct = abs(float(base["close"].iloc[-1]) - float(base["close"].iloc[0])) / float(base["close"].iloc[0]) * 100
    respects_range = float((base["close"].between(low * 0.99, high * 1.01)).mean()) >= 0.85
    volatility_contracting = not prior.empty and float(base["range_pct"].tail(20).mean()) < float(prior["range_pct"].tail(40).mean())
    volume_drying = not prior.empty and float(base["volume"].tail(20).mean()) < float(prior["volume"].tail(40).mean()) * 0.85
    sideways = depth_pct <= 25 and net_change_pct <= 12
    return {
        "base_high": high,
        "base_low": low,
        "base_depth_pct": depth_pct,
        "base_sideways": sideways,
        "base_respects_range": respects_range,
        "volatility_contracting": volatility_contracting,
        "base_volume_drying": volume_drying,
    }


def _cup_handle_metrics(frame: pd.DataFrame) -> dict[str, float | bool | None]:
    window = frame.tail(325).reset_index(drop=True)
    if len(window) < 150:
        return {"valid_cup": False, "valid_handle": False, "pivot": None}

    left_zone = window.iloc[:-25]
    left_idx = int(left_zone["high"].idxmax())
    low_idx = int(window.loc[left_idx:, "low"].idxmin())
    if low_idx <= left_idx:
        return {"valid_cup": False, "valid_handle": False, "pivot": None}

    left_high = float(window.loc[left_idx, "high"])
    cup_low = float(window.loc[low_idx, "low"])
    depth_pct = (left_high - cup_low) / left_high * 100
    prior_uptrend = left_idx >= 40 and float(window.loc[left_idx, "close"]) > float(window.loc[max(0, left_idx - 40), "close"]) * 1.12
    bottom = window.iloc[max(left_idx, low_idx - 10) : min(len(window), low_idx + 11)]
    bottom_volume_dry = float(bottom["volume"].mean()) < float(window.iloc[max(0, left_idx - 30) : left_idx]["volume"].mean()) * 0.9
    rounded_bottom = _is_rounded_bottom(window, left_idx, low_idx)

    best = None
    for handle_days in range(5, 26):
        handle_start = len(window) - handle_days
        right_zone = window.loc[low_idx : handle_start - 1]
        if len(right_zone) < 10:
            continue
        right_idx = int(right_zone["high"].idxmax())
        right_high = float(window.loc[right_idx, "high"])
        duration_days = right_idx - left_idx
        recovery = right_high / left_high if left_high else 0
        valid_cup = 12 <= depth_pct <= 35 and duration_days >= 30 and recovery >= 0.85
        if not valid_cup:
            continue

        handle = window.loc[handle_start:]
        handle_body = handle.iloc[:-1] if len(handle) > 6 else handle
        handle_high = float(handle_body["high"].max())
        pivot_zone = handle_body.iloc[:-1] if len(handle_body) > 1 else handle_body
        pivot = float(pivot_zone["high"].max())
        handle_low = float(handle_body["low"].min())
        handle_depth_pct = (handle_high - handle_low) / handle_high * 100 if handle_high else 0
        handle_upper_half = handle_low >= cup_low + (left_high - cup_low) / 2
        handle_volume_contracts = float(handle_body["volume"].mean()) < float(right_zone.tail(20)["volume"].mean()) * 0.9
        valid_handle = handle_upper_half and handle_depth_pct <= 15 and handle_volume_contracts
        if valid_handle:
            best = {
                "valid_cup": True,
                "valid_handle": True,
                "pivot": pivot,
                "cup_depth_pct": depth_pct,
                "cup_duration_days": duration_days,
                "prior_uptrend": prior_uptrend,
                "rounded_bottom": rounded_bottom,
                "right_side_recovery": recovery >= 0.85,
                "bottom_volume_dry": bottom_volume_dry,
                "handle_upper_half": handle_upper_half,
                "handle_depth_pct": handle_depth_pct,
                "handle_duration_days": handle_days,
                "handle_volume_contracts": handle_volume_contracts,
            }
            break

    if best is not None:
        return best

    return {
        "valid_cup": 12 <= depth_pct <= 35,
        "valid_handle": False,
        "pivot": left_high,
        "cup_depth_pct": depth_pct,
        "cup_duration_days": None,
        "prior_uptrend": prior_uptrend,
        "rounded_bottom": rounded_bottom,
        "right_side_recovery": False,
        "bottom_volume_dry": bottom_volume_dry,
        "handle_upper_half": False,
        "handle_depth_pct": None,
        "handle_duration_days": None,
        "handle_volume_contracts": False,
    }


def _score_stage_transition(
    frame: pd.DataFrame,
    base: dict[str, float | bool],
    cup: dict[str, float | bool | None],
    market_downtrend: bool,
) -> tuple[str, float, dict[str, bool]]:
    latest = frame.iloc[-1]
    close = float(latest["close"])
    above_mas = close > _safe_float(latest.get("ma_50"), float("inf")) and close > _safe_float(latest.get("ma_150"), float("inf")) and close > _safe_float(latest.get("ma_200"), float("inf"))
    ma_50_crossing = _safe_float(latest.get("ma_50")) >= min(_safe_float(latest.get("ma_150"), float("inf")), _safe_float(latest.get("ma_200"), float("inf"))) * 0.98
    ma_150_rising = _slope_pct(frame["ma_150"], 20) > 0
    ma_200_rising = _slope_pct(frame["ma_200"], 20) > 0
    ma_50_flattening = abs(_slope_pct(frame["ma_50"], 20)) <= 3
    long_mas_flat_or_up = _slope_pct(frame["ma_150"], 20) >= -1 and _slope_pct(frame["ma_200"], 20) >= -1
    base_breakout = bool(cup.get("pivot")) and close > float(cup["pivot"])
    near_base_high = close >= float(base["base_high"]) * 0.95
    base_quality = bool(base["base_sideways"]) and bool(base["base_respects_range"]) and bool(base["volatility_contracting"])

    score = 0.0
    score += 6 if above_mas else 0
    score += 4 if ma_50_crossing else 0
    score += 5 if ma_150_rising and ma_200_rising else 2.5 if ma_150_rising or ma_200_rising else 0
    score += 4 if base_breakout or near_base_high else 0
    score += 4 if base_quality else 0
    score += 2 if bool(base["base_volume_drying"]) else 0
    if market_downtrend:
        score = max(0, score - 3)

    if above_mas and (base_breakout or near_base_high) and ma_150_rising and ma_200_rising:
        stage = "Stage 2 advancing uptrend"
    elif bool(base["base_sideways"]) and ma_50_flattening and long_mas_flat_or_up:
        stage = "Stage 1 accumulation/base"
    elif close < _safe_float(latest.get("ma_150"), 0) and close < _safe_float(latest.get("ma_200"), 0):
        stage = "Stage 4 decline"
    else:
        stage = "Stage 3 distribution/transition"

    details = {
        "price_above_50_150_200": above_mas,
        "ma_50_above_or_crossing": ma_50_crossing,
        "ma_150_rising": ma_150_rising,
        "ma_200_rising": ma_200_rising,
        "base_breakout_or_near_high": base_breakout or near_base_high,
        "stage_1_base_quality": base_quality,
        "base_depth_pct": float(base["base_depth_pct"]),
    }
    return stage, min(25, round(score, 1)), details


def _score_cup_handle(cup: dict[str, float | bool | None]) -> tuple[float, str, dict[str, bool]]:
    if not cup.get("valid_cup"):
        return 0, "No valid cup", {"valid_cup": False, "valid_handle": False}

    score = 0.0
    score += 4 if cup.get("prior_uptrend") else 0
    score += 5 if _between(cup.get("cup_depth_pct"), 12, 35) else 0
    duration_days = _safe_float(cup.get("cup_duration_days"), 0) or 0
    score += 4 if duration_days >= 30 else 0
    score += 3 if cup.get("rounded_bottom") else 0
    score += 3 if cup.get("right_side_recovery") else 0
    score += 2 if cup.get("bottom_volume_dry") else 0
    score += 2 if cup.get("handle_upper_half") else 0
    score += 1 if _between(cup.get("handle_depth_pct"), 0, 15) else 0
    score += 1 if _between(cup.get("handle_duration_days"), 5, 25) else 0

    if cup.get("valid_handle"):
        status = "Valid cup and handle"
    elif cup.get("right_side_recovery"):
        status = "Cup formed; handle not ready"
    else:
        status = "Cup forming"
    return min(25, round(score, 1)), status, {"valid_cup": bool(cup.get("valid_cup")), "valid_handle": bool(cup.get("valid_handle"))}


def _score_volume(
    frame: pd.DataFrame,
    base: dict[str, float | bool],
    cup: dict[str, float | bool | None],
    breakout_volume_ratio: float,
) -> tuple[float, dict[str, bool | float | None]]:
    latest = frame.iloc[-1]
    volume_ratio = _safe_ratio(latest.get("volume"), latest.get("volume_ma_50"))
    breakout_volume_confirmed = volume_ratio is not None and volume_ratio >= breakout_volume_ratio
    handle_volume_contracts = bool(cup.get("handle_volume_contracts"))
    base_volume_drying = bool(base.get("base_volume_drying"))
    score = 0.0
    score += 10 if breakout_volume_confirmed else min(8, max(0, ((volume_ratio or 0) - 0.8) * 10))
    score += 3 if handle_volume_contracts else 0
    score += 2 if base_volume_drying else 0
    return min(15, round(score, 1)), {
        "volume_ratio": volume_ratio,
        "breakout_volume_confirmed": breakout_volume_confirmed,
        "handle_volume_contracts": handle_volume_contracts,
        "base_volume_drying": base_volume_drying,
    }


def _score_relative_strength(
    frame: pd.DataFrame,
    benchmark_daily: pd.DataFrame | None,
) -> tuple[float, dict[str, bool | float | None]]:
    work = frame.copy()
    if "rs_line" not in work.columns and benchmark_daily is not None and not benchmark_daily.empty:
        benchmark = _prepare_daily(benchmark_daily)[["date", "close"]].rename(columns={"close": "benchmark_close"})
        work = work.merge(benchmark, on="date", how="left")
        work["benchmark_close"] = work["benchmark_close"].ffill()
        work["rs_line"] = work["close"] / work["benchmark_close"]

    if "rs_line" not in work.columns:
        return 0, {"rs_trending_higher": False, "rs_20d_change": None, "rs_50d_change": None}

    work["rs_ma_20"] = work["rs_line"].rolling(20).mean()
    work["rs_ma_50"] = work["rs_line"].rolling(50).mean()
    rs_20d = _pct_change(work["rs_line"], 20)
    rs_50d = _pct_change(work["rs_line"], 50)
    latest = work.iloc[-1]
    rs_above_ma = _safe_float(latest.get("rs_line")) > _safe_float(latest.get("rs_ma_20"), float("inf"))
    rs_trending = rs_20d > 0 and rs_50d >= -2

    score = 0.0
    score += 6 if rs_20d > 0 else 0
    score += 5 if rs_50d > 0 else max(0, 5 + rs_50d)
    score += 4 if rs_above_ma else 0
    return min(15, round(score, 1)), {
        "rs_trending_higher": rs_trending,
        "rs_20d_change": round(rs_20d, 2),
        "rs_50d_change": round(rs_50d, 2),
    }


def _score_risk_reward(
    frame: pd.DataFrame,
    cup: dict[str, float | bool | None],
    max_extension_from_50d_pct: float,
) -> tuple[float, dict[str, bool | float | None]]:
    latest = frame.iloc[-1]
    close = float(latest["close"])
    pivot = cup.get("pivot")
    distance = _pct_distance_to_pivot(close, pivot)
    ma_50 = _safe_float(latest.get("ma_50"))
    extension = ((close - ma_50) / ma_50 * 100) if ma_50 else None
    handle_depth = _safe_float(cup.get("handle_depth_pct"))
    near_pivot = distance is not None and -3 <= distance <= 5
    not_extended = extension is not None and extension <= max_extension_from_50d_pct
    controlled_risk = handle_depth is not None and handle_depth <= 10

    score = 0.0
    score += 4 if near_pivot else 0
    score += 3 if not_extended else 0
    score += 3 if controlled_risk else 0
    return min(10, round(score, 1)), {
        "near_pivot": near_pivot,
        "not_extended_from_50d": not_extended,
        "controlled_handle_risk": controlled_risk,
        "distance_to_pivot_pct": distance,
        "extension_from_50d_pct": extension,
    }


def _score_market_condition(benchmark_daily: pd.DataFrame | None) -> tuple[float, bool]:
    if benchmark_daily is None or benchmark_daily.empty or len(benchmark_daily) < 200:
        return 5, False
    frame = _prepare_daily(benchmark_daily)
    latest = frame.iloc[-1]
    close = float(latest["close"])
    above_50 = close > _safe_float(latest.get("ma_50"), float("inf"))
    above_200 = close > _safe_float(latest.get("ma_200"), float("inf"))
    ma_50_rising = _slope_pct(frame["ma_50"], 20) > 0
    ma_200_rising = _slope_pct(frame["ma_200"], 20) > 0
    strong_downtrend = close < _safe_float(latest.get("ma_200"), 0) and _slope_pct(frame["ma_200"], 20) < -1

    score = 0.0
    score += 3 if above_50 else 0
    score += 3 if above_200 else 0
    score += 2 if ma_50_rising else 0
    score += 2 if ma_200_rising else 0
    if strong_downtrend:
        score = min(score, 3)
    return min(10, round(score, 1)), strong_downtrend


def _breakout_status(
    frame: pd.DataFrame,
    cup: dict[str, float | bool | None],
    breakout_volume_ratio: float,
    market_downtrend: bool,
    max_extension_from_50d_pct: float,
) -> str:
    pivot = cup.get("pivot")
    if not pivot:
        return "No breakout"
    latest = frame.iloc[-1]
    close = float(latest["close"])
    volume_ratio = _safe_ratio(latest.get("volume"), latest.get("volume_ma_50"))
    extension = _score_risk_reward(frame, cup, max_extension_from_50d_pct)[1]["extension_from_50d_pct"]
    previous_breakout = bool((frame["close"].tail(20) > float(pivot)).any())
    failed = previous_breakout and close < float(pivot)
    if failed:
        return "Failed breakout"
    if close > float(pivot) and volume_ratio is not None and volume_ratio >= breakout_volume_ratio and not market_downtrend:
        return "Confirmed breakout"
    if close >= float(pivot) * 0.97 and close <= float(pivot) and bool(cup.get("valid_handle")):
        return "Near pivot"
    if extension is not None and extension > max_extension_from_50d_pct:
        return "Extended"
    return "No breakout"


def _classify(
    scores: CriteriaScores,
    stage: str,
    cup_status: str,
    breakout_status: str,
    extended_from_50d_pct: float | None,
) -> str:
    if breakout_status == "Failed breakout":
        return CLASS_FAILED_BREAKOUT
    if extended_from_50d_pct is not None and extended_from_50d_pct > 12 and breakout_status != "Confirmed breakout":
        return CLASS_EXTENDED
    if breakout_status == "Confirmed breakout":
        if extended_from_50d_pct is not None and extended_from_50d_pct > 15:
            return CLASS_EXTENDED
        return CLASS_BREAKOUT_CONFIRMED
    if breakout_status == "Near pivot" and scores.total >= 70:
        return CLASS_BREAKOUT_CANDIDATE
    if stage == "Stage 2 advancing uptrend" and cup_status == "Valid cup and handle" and scores.total >= 65:
        return CLASS_STRONG_WATCH
    if scores.total >= 55 or stage == "Stage 1 accumulation/base":
        return CLASS_EARLY_WATCH
    return CLASS_IGNORE


def _build_notes(
    classification: str,
    stage: str,
    cup_status: str,
    breakout_status: str,
    scores: CriteriaScores,
) -> tuple[str, ...]:
    return (
        f"Classification: {classification}.",
        f"Stage: {stage}. Cup/handle: {cup_status}. Breakout: {breakout_status}.",
        f"Score: {scores.total}/100.",
    )


def _is_rounded_bottom(window: pd.DataFrame, left_idx: int, low_idx: int) -> bool:
    right_span = min(len(window) - 1, low_idx + max(10, low_idx - left_idx))
    left_leg = window.loc[left_idx:low_idx, "close"]
    right_leg = window.loc[low_idx:right_span, "close"]
    return float(left_leg.diff().dropna().median()) < 0 and float(right_leg.diff().dropna().median()) > 0


def _safe_float(value: object, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result):
        return default
    return result


def _safe_ratio(numerator: object, denominator: object) -> float | None:
    numerator_float = _safe_float(numerator)
    denominator_float = _safe_float(denominator)
    if numerator_float is None or denominator_float is None or denominator_float <= 0:
        return None
    return numerator_float / denominator_float


def _slope_pct(series: pd.Series, periods: int) -> float:
    clean = series.dropna()
    if len(clean) <= periods:
        return 0
    start = float(clean.iloc[-periods - 1])
    end = float(clean.iloc[-1])
    if start == 0:
        return 0
    return (end - start) / start * 100


def _pct_change(series: pd.Series, periods: int) -> float:
    clean = series.dropna()
    if len(clean) <= periods:
        return 0
    start = float(clean.iloc[-periods - 1])
    end = float(clean.iloc[-1])
    if start == 0:
        return 0
    return (end - start) / start * 100


def _pct_distance_to_pivot(close: float, pivot: object) -> float | None:
    pivot_float = _safe_float(pivot)
    if pivot_float is None or pivot_float == 0:
        return None
    return round((pivot_float - close) / pivot_float * 100, 2)


def _between(value: object, low: float, high: float) -> bool:
    value_float = _safe_float(value)
    return value_float is not None and low <= value_float <= high
