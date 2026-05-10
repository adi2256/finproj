-- ============================================================
-- Migration 002 — Phase 3: Sentiment Model Tables
-- Run: psql -U finance_user -d financedb -f db/migrations/002_phase3_sentiment.sql
-- ============================================================

-- Daily aggregated sentiment per ticker (feature for forecasting model)
CREATE TABLE IF NOT EXISTS daily_sentiment_agg (
    id              BIGSERIAL     PRIMARY KEY,
    ticker          VARCHAR(16)   NOT NULL REFERENCES stocks(ticker),
    date            DATE          NOT NULL,
    avg_score       NUMERIC(6,4),
    min_score       NUMERIC(6,4),
    max_score       NUMERIC(6,4),
    article_count   INTEGER       NOT NULL DEFAULT 0,
    positive_pct    NUMERIC(5,2),
    negative_pct    NUMERIC(5,2),
    neutral_pct     NUMERIC(5,2),
    computed_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_dsa_ticker_date ON daily_sentiment_agg (ticker, date DESC);

-- Filing-level sentiment (year-over-year comparison for MD&A)
CREATE TABLE IF NOT EXISTS filing_sentiment (
    id              BIGSERIAL     PRIMARY KEY,
    filing_id       BIGINT        NOT NULL REFERENCES filings(id),
    ticker          VARCHAR(16)   NOT NULL REFERENCES stocks(ticker),
    period          DATE          NOT NULL,
    avg_score       NUMERIC(6,4),
    label           VARCHAR(16),
    prev_period_score NUMERIC(6,4),
    score_delta     NUMERIC(6,4),
    model_version   VARCHAR(64),
    computed_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (filing_id)
);

CREATE INDEX IF NOT EXISTS idx_fs_ticker_period ON filing_sentiment (ticker, period DESC);
