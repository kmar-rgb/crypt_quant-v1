from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import CmcEnvelope, CryptoAsset, MarketQuote


LOGGER = logging.getLogger(__name__)


class CoinMarketCapError(RuntimeError):
    pass


class CoinMarketCapClient:
    base_url = "https://pro-api.coinmarketcap.com"

    def __init__(
        self,
        api_key: str,
        timeout_seconds: int = 20,
        max_retries: int = 3,
        base_url: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("CoinMarketCap API key is required.")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        if base_url:
            self.base_url = base_url.rstrip("/")

    def cryptocurrency_map(self, *, start: int = 1, limit: int = 500) -> CmcEnvelope:
        return self._get("/v1/cryptocurrency/map", {"start": start, "limit": limit})

    def listings_latest(self, *, start: int = 1, limit: int = 500, convert: str = "USD") -> CmcEnvelope:
        return self._get(
            "/v1/cryptocurrency/listings/latest",
            {"start": start, "limit": limit, "convert": convert},
        )

    def quotes_latest(self, *, ids: list[int], convert: str = "USD") -> CmcEnvelope:
        return self._get(
            "/v1/cryptocurrency/quotes/latest",
            {"id": ",".join(str(item) for item in ids), "convert": convert},
        )

    def global_metrics_latest(self, *, convert: str = "USD") -> CmcEnvelope:
        return self._get("/v1/global-metrics/quotes/latest", {"convert": convert})

    def parse_listing_assets_and_quotes(self, envelope: CmcEnvelope, currency: str = "USD") -> tuple[list[CryptoAsset], list[MarketQuote]]:
        assets: list[CryptoAsset] = []
        quotes: list[MarketQuote] = []
        rows = envelope.data if isinstance(envelope.data, list) else []
        source_timestamp = envelope.status.timestamp
        for row in rows:
            quote_data = (row.get("quote") or {}).get(currency) or {}
            market_cap = _float_or_none(quote_data.get("market_cap"))
            volume_24h = _float_or_none(quote_data.get("volume_24h"))
            volume_to_market_cap = volume_24h / market_cap if market_cap and volume_24h is not None else None
            assets.append(
                CryptoAsset(
                    cmc_id=int(row["id"]),
                    symbol=str(row.get("symbol", "")).upper(),
                    name=str(row.get("name", "")),
                    slug=row.get("slug"),
                    category=row.get("category"),
                    market_cap_rank=row.get("cmc_rank"),
                    circulating_supply=_float_or_none(row.get("circulating_supply")),
                    max_supply=_float_or_none(row.get("max_supply")),
                    tags=list(row.get("tags") or []),
                    metadata_updated_at=_parse_datetime(row.get("last_updated")),
                )
            )
            quotes.append(
                MarketQuote(
                    cmc_id=int(row["id"]),
                    currency=currency,
                    price=_float_or_none(quote_data.get("price")),
                    market_cap=market_cap,
                    volume_24h=volume_24h,
                    volume_to_market_cap=volume_to_market_cap,
                    percent_change_24h=_float_or_none(quote_data.get("percent_change_24h")),
                    percent_change_7d=_float_or_none(quote_data.get("percent_change_7d")),
                    percent_change_30d=_float_or_none(quote_data.get("percent_change_30d")),
                    percent_change_90d=_float_or_none(quote_data.get("percent_change_90d")),
                    last_updated=_parse_datetime(quote_data.get("last_updated") or row.get("last_updated")),
                    source_updated_at=source_timestamp,
                )
            )
        return assets, quotes

    def _get(self, path: str, params: dict[str, Any]) -> CmcEnvelope:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        url = f"{self.base_url}{path}?{query}" if query else f"{self.base_url}{path}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "X-CMC_PRO_API_KEY": self.api_key,
            },
        )

        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                envelope = CmcEnvelope(**payload)
                if envelope.status.error_code:
                    raise CoinMarketCapError(str(envelope.status.error_message))
                return envelope
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= self.max_retries:
                    raise CoinMarketCapError(f"CoinMarketCap request failed with HTTP {exc.code}") from exc
                _sleep_before_retry(attempt)
            except (URLError, TimeoutError) as exc:
                if attempt >= self.max_retries:
                    raise CoinMarketCapError("CoinMarketCap request failed after retries.") from exc
                _sleep_before_retry(attempt)
        raise CoinMarketCapError("CoinMarketCap request failed.")


def _sleep_before_retry(attempt: int) -> None:
    delay = min(2**attempt, 30)
    LOGGER.info("Retrying CoinMarketCap request after transient failure.", extra={"delay_seconds": delay})
    time.sleep(delay)


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
