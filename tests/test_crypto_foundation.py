from __future__ import annotations

import unittest
from importlib.util import find_spec

from crypto_quant.cmc_client import CoinMarketCapClient
from crypto_quant.config import load_app_settings
from crypto_quant.models import CmcEnvelope, MarketStage, Rating, ScoreBreakdown
from crypto_quant.services.scoring import assign_rating, calculate_weighted_score


class CryptoFoundationTests(unittest.TestCase):
    def test_settings_load_default_thresholds(self) -> None:
        settings = load_app_settings()
        self.assertGreaterEqual(settings.scoring.buy_threshold, settings.scoring.watch_threshold)
        self.assertGreater(settings.filters.minimum_market_cap, 0)
        self.assertIn("AUD", settings.scan.display_currencies)

    def test_score_formula_keeps_five_point_scale(self) -> None:
        settings = load_app_settings()
        breakdown = ScoreBreakdown(
            stage_trend=1,
            breakout_structure=0.75,
            volume_liquidity=0.5,
            momentum_relative_strength=0.75,
            risk_entry_quality=1,
        )
        raw, display = calculate_weighted_score(breakdown, settings.scoring)
        self.assertAlmostEqual(raw, 4.0)
        self.assertEqual(display, 4.0)

    def test_rating_rejects_stage_four_even_with_high_score(self) -> None:
        settings = load_app_settings()
        rating = assign_rating(
            raw_score=4.8,
            stage=MarketStage.STAGE_4,
            liquidity_passed=True,
            risk_reward=3.0,
            excessive_extension=False,
            critical_risk_flags=[],
            settings=settings.scoring,
        )
        self.assertEqual(rating, Rating.AVOID)

    def test_cmc_listing_parser_maps_assets_and_quotes(self) -> None:
        client = CoinMarketCapClient(api_key="test-key")
        envelope = CmcEnvelope(
            data=[
                {
                    "id": 1,
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "slug": "bitcoin",
                    "cmc_rank": 1,
                    "circulating_supply": 19_000_000,
                    "max_supply": 21_000_000,
                    "tags": ["mineable"],
                    "last_updated": "2026-07-10T00:00:00.000Z",
                    "quote": {
                        "USD": {
                            "price": 100000,
                            "market_cap": 1900000000000,
                            "volume_24h": 50000000000,
                            "percent_change_24h": 1.5,
                            "percent_change_7d": 3.0,
                            "percent_change_30d": 10.0,
                            "percent_change_90d": 25.0,
                            "last_updated": "2026-07-10T00:00:00.000Z",
                        }
                    },
                }
            ],
            status={"timestamp": "2026-07-10T00:00:01.000Z", "credit_count": 1},
        )
        assets, quotes = client.parse_listing_assets_and_quotes(envelope)
        self.assertEqual(assets[0].cmc_id, 1)
        self.assertEqual(quotes[0].volume_to_market_cap, 50000000000 / 1900000000000)

    def test_repository_saves_screener_rows(self) -> None:
        if find_spec("sqlalchemy") is None:
            self.skipTest("SQLAlchemy is not installed in this runtime.")
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from crypto_quant.db_models import Base
        from crypto_quant.repositories import CryptoRepository

        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, future=True)
        client = CoinMarketCapClient(api_key="test-key")
        envelope = CmcEnvelope(
            data=[
                {
                    "id": 1027,
                    "name": "Ethereum",
                    "symbol": "ETH",
                    "slug": "ethereum",
                    "cmc_rank": 2,
                    "tags": [],
                    "quote": {"USD": {"price": 3000, "market_cap": 360000000000, "volume_24h": 15000000000}},
                }
            ],
            status={"timestamp": "2026-07-10T00:00:01.000Z"},
        )
        assets, quotes = client.parse_listing_assets_and_quotes(envelope)
        with Session() as session:
            repo = CryptoRepository(session)
            repo.upsert_asset(assets[0])
            repo.upsert_quote(quotes[0])
            session.commit()
            rows = repo.latest_screener_rows()
        self.assertEqual(rows[0].symbol, "ETH")
        self.assertEqual(rows[0].rating, Rating.AVOID)


if __name__ == "__main__":
    unittest.main()
