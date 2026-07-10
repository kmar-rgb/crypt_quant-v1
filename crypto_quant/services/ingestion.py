from __future__ import annotations

from sqlalchemy.orm import Session

from crypto_quant.cmc_client import CoinMarketCapClient
from crypto_quant.models import IngestResult
from crypto_quant.repositories import CryptoRepository


class MarketDataIngestionService:
    def __init__(self, client: CoinMarketCapClient, session: Session):
        self.client = client
        self.repository = CryptoRepository(session)

    def ingest_latest_listings(self, *, limit: int, currency: str) -> IngestResult:
        envelope = self.client.listings_latest(start=1, limit=limit, convert=currency)
        assets, quotes = self.client.parse_listing_assets_and_quotes(envelope, currency=currency)
        for asset in assets:
            self.repository.upsert_asset(asset)
        for quote in quotes:
            self.repository.upsert_quote(quote)
        warnings = []
        if not assets:
            warnings.append("CoinMarketCap returned no listing rows.")
        return IngestResult(assets_seen=len(assets), quotes_saved=len(quotes), currency=currency, warnings=warnings)
