from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db_models import Cryptocurrency, MarketQuoteRow
from .models import CryptoAsset, DataQualityStatus, MarketQuote, MarketStage, Rating, ScreenerRow


class CryptoRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_asset(self, asset: CryptoAsset) -> None:
        row = self.session.get(Cryptocurrency, asset.cmc_id)
        if row is None:
            row = Cryptocurrency(cmc_id=asset.cmc_id, symbol=asset.symbol, name=asset.name)
            self.session.add(row)
        row.symbol = asset.symbol
        row.name = asset.name
        row.slug = asset.slug
        row.category = asset.category
        row.tags_json = json.dumps(asset.tags)
        row.market_cap_rank = asset.market_cap_rank
        row.circulating_supply = asset.circulating_supply
        row.max_supply = asset.max_supply
        row.metadata_updated_at = asset.metadata_updated_at

    def upsert_quote(self, quote: MarketQuote) -> None:
        statement = select(MarketQuoteRow).where(
            MarketQuoteRow.cmc_id == quote.cmc_id,
            MarketQuoteRow.currency == quote.currency,
        )
        row = self.session.execute(statement).scalar_one_or_none()
        if row is None:
            row = MarketQuoteRow(cmc_id=quote.cmc_id, currency=quote.currency)
            self.session.add(row)
        row.price = quote.price
        row.market_cap = quote.market_cap
        row.volume_24h = quote.volume_24h
        row.volume_to_market_cap = quote.volume_to_market_cap
        row.percent_change_24h = quote.percent_change_24h
        row.percent_change_7d = quote.percent_change_7d
        row.percent_change_30d = quote.percent_change_30d
        row.percent_change_90d = quote.percent_change_90d
        row.last_updated = quote.last_updated
        row.source_updated_at = quote.source_updated_at

    def latest_screener_rows(self, currency: str = "USD", limit: int = 500) -> list[ScreenerRow]:
        statement = (
            select(Cryptocurrency, MarketQuoteRow)
            .join(MarketQuoteRow, MarketQuoteRow.cmc_id == Cryptocurrency.cmc_id)
            .where(MarketQuoteRow.currency == currency)
            .order_by(Cryptocurrency.market_cap_rank.is_(None), Cryptocurrency.market_cap_rank)
            .limit(limit)
        )
        rows: list[ScreenerRow] = []
        for asset, quote in self.session.execute(statement).all():
            missing = []
            if quote.price is None:
                missing.append("price")
            if quote.market_cap is None:
                missing.append("market_cap")
            if quote.volume_24h is None:
                missing.append("volume_24h")
            data_quality = DataQualityStatus.PARTIAL if missing else DataQualityStatus.MISSING_HISTORY
            rows.append(
                ScreenerRow(
                    cmc_id=asset.cmc_id,
                    rank=asset.market_cap_rank,
                    name=asset.name,
                    symbol=asset.symbol,
                    price=quote.price,
                    percent_change_24h=quote.percent_change_24h,
                    percent_change_7d=quote.percent_change_7d,
                    percent_change_30d=quote.percent_change_30d,
                    percent_change_90d=quote.percent_change_90d,
                    market_cap=quote.market_cap,
                    volume_24h=quote.volume_24h,
                    volume_to_market_cap=quote.volume_to_market_cap,
                    stage=MarketStage.INSUFFICIENT_DATA,
                    stage_confidence=0.0,
                    raw_score=0.0,
                    display_score=0.0,
                    rating=Rating.AVOID,
                    data_quality_status=data_quality,
                    last_updated=quote.last_updated,
                    missing_data=["price_history", *missing],
                )
            )
        return rows
