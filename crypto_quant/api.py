from __future__ import annotations

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from .cmc_client import CoinMarketCapClient, CoinMarketCapError
from .config import load_app_settings, load_runtime_settings, public_settings
from .database import database_online, engine_from_url, init_db, session_factory
from .models import HealthCheck, IngestResult, ScreenerRow
from .repositories import CryptoRepository
from .services.ingestion import MarketDataIngestionService


app = FastAPI(
    title="Crypto Quant Research Dashboard API",
    version="0.1.0",
    description="Deterministic cryptocurrency research dashboard backend.",
)

ENGINE = engine_from_url()
SessionLocal = session_factory(ENGINE)


def get_session() -> Session:
    init_db(ENGINE)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@app.get("/health", response_model=HealthCheck)
def health() -> HealthCheck:
    runtime = load_runtime_settings()
    return HealthCheck(
        status="ok" if database_online(ENGINE) else "degraded",
        app_env=runtime.app_env,
        database_configured=bool(runtime.database_url),
        coinmarketcap_configured=bool(runtime.coinmarketcap_api_key),
        timestamp=datetime.utcnow(),
    )


@app.get("/api/v1/settings")
def settings() -> dict:
    return public_settings(load_app_settings())


@app.get("/api/v1/screener", response_model=list[ScreenerRow])
def screener(
    currency: str = Query(default="USD", min_length=3, max_length=12),
    limit: int = Query(default=500, ge=1, le=5000),
    session: Session = Depends(get_session),
) -> list[ScreenerRow]:
    repository = CryptoRepository(session)
    return repository.latest_screener_rows(currency=currency.upper(), limit=limit)


@app.post("/api/v1/scans/coinmarketcap", response_model=IngestResult)
def scan_coinmarketcap(
    limit: int = Query(default=100, ge=1, le=5000),
    currency: str = Query(default="USD", min_length=3, max_length=12),
    session: Session = Depends(get_session),
) -> IngestResult:
    runtime = load_runtime_settings()
    app_settings = load_app_settings()
    if not runtime.coinmarketcap_api_key:
        raise HTTPException(status_code=400, detail="COINMARKETCAP_API_KEY is not configured.")
    client = CoinMarketCapClient(
        api_key=runtime.coinmarketcap_api_key,
        timeout_seconds=app_settings.data.request_timeout_seconds,
        max_retries=app_settings.data.max_retries,
    )
    service = MarketDataIngestionService(client, session)
    try:
        return service.ingest_latest_listings(limit=limit, currency=currency.upper())
    except CoinMarketCapError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
