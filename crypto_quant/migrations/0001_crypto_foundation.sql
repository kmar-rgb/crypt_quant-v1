CREATE TABLE IF NOT EXISTS cryptocurrencies (
    cmc_id INTEGER PRIMARY KEY,
    symbol VARCHAR(32) NOT NULL,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255),
    category VARCHAR(120),
    tags_json TEXT NOT NULL DEFAULT '[]',
    market_cap_rank INTEGER,
    circulating_supply REAL,
    max_supply REAL,
    metadata_updated_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS market_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cmc_id INTEGER NOT NULL,
    currency VARCHAR(12) NOT NULL DEFAULT 'USD',
    price REAL,
    market_cap REAL,
    volume_24h REAL,
    volume_to_market_cap REAL,
    percent_change_24h REAL,
    percent_change_7d REAL,
    percent_change_30d REAL,
    percent_change_90d REAL,
    last_updated DATETIME,
    source_updated_at DATETIME,
    created_at DATETIME NOT NULL,
    CONSTRAINT uq_market_quotes_asset_currency UNIQUE (cmc_id, currency),
    FOREIGN KEY (cmc_id) REFERENCES cryptocurrencies(cmc_id)
);

CREATE TABLE IF NOT EXISTS application_settings (
    key VARCHAR(120) PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type VARCHAR(120) NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at DATETIME NOT NULL
);
