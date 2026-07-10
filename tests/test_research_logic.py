from __future__ import annotations

import unittest

import pandas as pd

from stock_research_agent.backtesting import backtest_breakout_follow_through, summarize_trades
from stock_research_agent.indicators import add_moving_averages, add_relative_strength, to_weekly
from stock_research_agent.patterns import detect_cup_handle
from stock_research_agent.scoring import score_candidate
from stock_research_agent.stage_analysis import detect_stage


def make_trending_frame(days: int = 320) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=days, freq="B")
    close = pd.Series(range(days), dtype=float) * 0.15 + 50
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.2,
            "high": close + 0.8,
            "low": close - 0.8,
            "close": close,
            "volume": 1_000_000 + pd.Series(range(days)) * 1_000,
        }
    )


def make_cup_handle_frame() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=170, freq="B")
    values = (
        list(pd.Series(range(30), dtype=float) * 0.3 + 91)
        + list(pd.Series(range(35), dtype=float).map(lambda item: 100 - item * 0.7))
        + list(pd.Series(range(55), dtype=float).map(lambda item: 75.5 + item * 0.42))
        + list(pd.Series(range(20), dtype=float).map(lambda item: 98 - item * 0.2))
        + list(pd.Series(range(30), dtype=float).map(lambda item: 94 + item * 0.35))
    )
    close = pd.Series(values[:170])
    close.iloc[-1] = 101
    volume = pd.Series([1_000_000] * 169 + [1_700_000])
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.3,
            "high": close + 0.8,
            "low": close - 0.8,
            "close": close,
            "volume": volume,
        }
    )


class ResearchLogicTests(unittest.TestCase):
    def test_indicators_and_relative_strength(self) -> None:
        stock = add_moving_averages(make_trending_frame())
        benchmark = add_moving_averages(make_trending_frame())
        result = add_relative_strength(stock, benchmark)
        self.assertIn("ma_200", result.columns)
        self.assertIn("rs_50d_change", result.columns)
        self.assertFalse(result["ma_200"].dropna().empty)

    def test_stage_two_detection(self) -> None:
        daily = add_moving_averages(make_trending_frame())
        weekly = to_weekly(make_trending_frame())
        stage = detect_stage(daily, weekly)
        self.assertEqual(stage.stage, "Stage 2 uptrend")

    def test_cup_handle_breakout_detection(self) -> None:
        daily = add_moving_averages(make_cup_handle_frame())
        result = detect_cup_handle(daily)
        self.assertEqual(result.status, "Breakout")
        self.assertIsNotNone(result.pivot)

    def test_scoring_returns_total(self) -> None:
        daily = add_moving_averages(make_cup_handle_frame())
        benchmark = add_moving_averages(make_trending_frame(170))
        daily = add_relative_strength(daily, benchmark)
        stage = detect_stage(add_moving_averages(make_trending_frame()), to_weekly(make_trending_frame()))
        pattern = detect_cup_handle(daily)
        score = score_candidate(daily, stage, pattern)
        self.assertGreater(score.total, 40)

    def test_backtest_summary_shape(self) -> None:
        trades = backtest_breakout_follow_through(make_trending_frame(), pivot_lookback=40, hold_days=10, volume_ratio=0.8)
        summary = summarize_trades(trades)
        self.assertIn("trades", summary)
        self.assertIn("average_return_pct", summary)


if __name__ == "__main__":
    unittest.main()
