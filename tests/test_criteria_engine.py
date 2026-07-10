from __future__ import annotations

import unittest

import pandas as pd

from stock_research_agent.criteria_engine import (
    CLASS_BREAKOUT_CONFIRMED,
    CLASS_EARLY_WATCH,
    CLASS_EXTENDED,
    CLASS_FAILED_BREAKOUT,
    CLASS_IGNORE,
    evaluate_stock_criteria,
)
from stock_research_agent.backtesting import backtest_cup_handle_breakouts, summarize_cup_handle_backtest


def frame_from_closes(closes: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="B")
    close = pd.Series(closes, dtype=float)
    if volumes is None:
        volumes = [1_000_000] * len(closes)
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.3,
            "high": close + 0.8,
            "low": close - 0.8,
            "close": close,
            "volume": volumes,
        }
    )


def breakout_candidate_frame() -> pd.DataFrame:
    closes = (
        list(_line(45, 100, 60))
        + list(_line(100, 72, 45))
        + list(_line(72, 98, 75))
        + list(_line(97, 93, 8))
        + list(_line(93, 96, 11))
        + [100.5]
    )
    volumes = (
        [1_200_000] * 60
        + [950_000] * 30
        + [700_000] * 15
        + [1_000_000] * 75
        + [650_000] * 19
        + [1_800_000]
    )
    return frame_from_closes(closes, volumes)


def benchmark_uptrend(days: int) -> pd.DataFrame:
    return frame_from_closes(list(_line(80, 100, days)), [1_000_000] * days)


def benchmark_downtrend(days: int) -> pd.DataFrame:
    return frame_from_closes(list(_line(120, 80, days)), [1_000_000] * days)


def stage_one_base_frame() -> pd.DataFrame:
    closes = list(_line(70, 88, 120)) + [86, 85, 87, 86, 88, 87, 86, 87, 88, 86] * 9
    volumes = [1_200_000] * 120 + [700_000] * 90
    return frame_from_closes(closes, volumes)


def extended_frame() -> pd.DataFrame:
    frame = breakout_candidate_frame()
    frame.loc[frame.index[-1], "close"] = 122
    frame.loc[frame.index[-1], "high"] = 123
    frame.loc[frame.index[-1], "low"] = 120
    frame.loc[frame.index[-1], "open"] = 121
    frame.loc[frame.index[-1], "volume"] = 1_000_000
    return frame


def failed_breakout_frame() -> pd.DataFrame:
    frame = breakout_candidate_frame()
    prior = frame.index[-2]
    last = frame.index[-1]
    frame.loc[prior, ["open", "high", "low", "close", "volume"]] = [99, 101, 98, 100.2, 1_800_000]
    frame.loc[last, ["open", "high", "low", "close", "volume"]] = [95, 96, 93, 94, 1_400_000]
    return frame


def weak_downtrend_frame() -> pd.DataFrame:
    return frame_from_closes(list(_line(100, 55, 220)), [1_000_000] * 220)


class CriteriaEngineTests(unittest.TestCase):
    def test_confirmed_breakout_scores_requested_categories(self) -> None:
        frame = breakout_candidate_frame()
        result = evaluate_stock_criteria(frame, benchmark_uptrend(len(frame)))
        self.assertEqual(result.classification, CLASS_BREAKOUT_CONFIRMED)
        self.assertEqual(result.breakout_status, "Confirmed breakout")
        self.assertGreaterEqual(result.scores.total, 70)
        self.assertLessEqual(result.scores.stage_2_transition, 25)
        self.assertLessEqual(result.scores.cup_handle_quality, 25)
        self.assertLessEqual(result.scores.volume_confirmation, 15)
        self.assertLessEqual(result.scores.relative_strength, 15)
        self.assertLessEqual(result.scores.risk_reward, 10)
        self.assertLessEqual(result.scores.market_condition, 10)

    def test_stage_one_base_becomes_early_watch(self) -> None:
        frame = stage_one_base_frame()
        result = evaluate_stock_criteria(frame, benchmark_uptrend(len(frame)))
        self.assertEqual(result.stage, "Stage 1 accumulation/base")
        self.assertEqual(result.classification, CLASS_EARLY_WATCH)

    def test_extended_move_is_too_late(self) -> None:
        frame = extended_frame()
        result = evaluate_stock_criteria(frame, benchmark_uptrend(len(frame)))
        self.assertEqual(result.classification, CLASS_EXTENDED)

    def test_failed_breakout_has_priority_classification(self) -> None:
        frame = failed_breakout_frame()
        result = evaluate_stock_criteria(frame, benchmark_uptrend(len(frame)))
        self.assertEqual(result.classification, CLASS_FAILED_BREAKOUT)
        self.assertEqual(result.breakout_status, "Failed breakout")

    def test_weak_downtrend_is_ignored(self) -> None:
        frame = weak_downtrend_frame()
        result = evaluate_stock_criteria(frame, benchmark_downtrend(len(frame)))
        self.assertEqual(result.classification, CLASS_IGNORE)

    def test_cup_handle_backtest_reports_metrics(self) -> None:
        frame = breakout_candidate_frame()
        future = frame_from_closes(list(_line(102, 110, 30)), [1_000_000] * 30)
        future["date"] = pd.bdate_range(frame["date"].iloc[-1] + pd.Timedelta(days=1), periods=len(future))
        combined = pd.concat([frame, future], ignore_index=True)
        trades = backtest_cup_handle_breakouts(combined, benchmark_uptrend(len(combined)), min_score=50, hold_days=5)
        summary = summarize_cup_handle_backtest(trades)
        self.assertGreaterEqual(summary["trades"], 1)
        self.assertIn("performance_by_score_range", summary)


def _line(start: float, end: float, count: int):
    if count == 1:
        yield end
        return
    step = (end - start) / (count - 1)
    for index in range(count):
        yield start + step * index


if __name__ == "__main__":
    unittest.main()
