-- ============================================================
-- Migration 001 — Phase 2: Feature Engineering Tables
-- Run: psql -U finance_user -d financedb -f db/migrations/001_phase2_tables.sql
-- ============================================================

-- Technical indicators (one row per ticker-date after OHLCV ingest)
CREATE TABLE IF NOT EXISTS technical_features (
    id              BIGSERIAL     PRIMARY KEY,
    ticker          VARCHAR(16)   NOT NULL REFERENCES stocks(ticker),
    date            DATE          NOT NULL,

    -- Moving averages
    sma_20          NUMERIC(18,6),
    sma_50          NUMERIC(18,6),
    sma_200         NUMERIC(18,6),
    ema_20          NUMERIC(18,6),
    ema_50          NUMERIC(18,6),
    ema_200         NUMERIC(18,6),

    -- Momentum
    rsi_14          NUMERIC(8,4),
    macd            NUMERIC(18,6),
    macd_signal     NUMERIC(18,6),
    macd_hist       NUMERIC(18,6),

    -- Volatility / Bands
    bb_upper        NUMERIC(18,6),
    bb_mid          NUMERIC(18,6),
    bb_lower        NUMERIC(18,6),
    bb_pct          NUMERIC(8,4),   -- (close - bb_lower) / (bb_upper - bb_lower)
    atr_14          NUMERIC(18,6),

    -- Volume
    obv             BIGINT,
    volume_zscore   NUMERIC(8,4),   -- z-score vs trailing 20-day volume

    -- Returns (used as targets / cross-sectional features)
    daily_return    NUMERIC(10,6),
    log_return      NUMERIC(10,6),
    rolling_vol_20  NUMERIC(10,6),  -- 20-day realised volatility (annualised)

    computed_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_tf_ticker_date ON technical_features (ticker, date DESC);

-- Fundamental ratios (one row per ticker-fiscal-period, sourced from yfinance)
CREATE TABLE IF NOT EXISTS fundamental_features (
    id               BIGSERIAL     PRIMARY KEY,
    ticker           VARCHAR(16)   NOT NULL REFERENCES stocks(ticker),
    period           DATE          NOT NULL,   -- fiscal period end date
    filing_id        BIGINT        REFERENCES filings(id),

    -- Valuation
    pe_ratio         NUMERIC(12,4),
    pb_ratio         NUMERIC(12,4),
    ps_ratio         NUMERIC(12,4),
    ev_ebitda        NUMERIC(12,4),

    -- Growth
    revenue_qoq      NUMERIC(10,4),   -- QoQ revenue growth
    revenue_yoy      NUMERIC(10,4),   -- YoY revenue growth
    earnings_growth  NUMERIC(10,4),

    -- Profitability
    gross_margin     NUMERIC(10,4),
    operating_margin NUMERIC(10,4),
    net_margin       NUMERIC(10,4),
    roe              NUMERIC(10,4),   -- return on equity
    roa              NUMERIC(10,4),   -- return on assets

    -- Per-share
    eps_actual       NUMERIC(12,4),
    eps_estimate     NUMERIC(12,4),
    eps_surprise     NUMERIC(10,4),   -- (actual - estimate) / |estimate| * 100

    -- Health / leverage
    debt_to_equity   NUMERIC(12,4),
    current_ratio    NUMERIC(12,4),
    quick_ratio      NUMERIC(12,4),

    computed_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (ticker, period)
);

CREATE INDEX IF NOT EXISTS idx_ff_ticker_period ON fundamental_features (ticker, period DESC);

-- Sector-level aggregate analytics (daily rollup)
CREATE TABLE IF NOT EXISTS sector_analytics (
    id                BIGSERIAL     PRIMARY KEY,
    sector            VARCHAR(64)   NOT NULL,
    date              DATE          NOT NULL,

    avg_return        NUMERIC(10,6),
    median_return     NUMERIC(10,6),
    return_dispersion NUMERIC(10,6),  -- cross-sectional std of returns
    rolling_vol_avg   NUMERIC(10,6),  -- avg 20-day vol across tickers
    max_drawdown      NUMERIC(10,6),  -- worst peak-to-trough in rolling 252d window
    vol_anomaly_pct   NUMERIC(6,2),   -- % tickers with volume z-score > 2

    computed_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (sector, date)
);

CREATE INDEX IF NOT EXISTS idx_sa_sector_date ON sector_analytics (sector, date DESC);
