-- ============================================================
-- Finance Project — PostgreSQL Schema
-- Run once: psql -U finance_user -d financedb -f schema.sql
-- ============================================================

-- Stock universe
CREATE TABLE IF NOT EXISTS stocks (
    ticker          VARCHAR(16)  PRIMARY KEY,
    name            VARCHAR(255),
    sector          VARCHAR(64),
    market_cap      BIGINT,
    exchange        VARCHAR(16),
    active          BOOLEAN      NOT NULL DEFAULT TRUE,
    added_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Daily OHLCV prices
CREATE TABLE IF NOT EXISTS ohlcv (
    id              BIGSERIAL    PRIMARY KEY,
    ticker          VARCHAR(16)  NOT NULL REFERENCES stocks(ticker),
    date            DATE         NOT NULL,
    open            NUMERIC(18,6),
    high            NUMERIC(18,6),
    low             NUMERIC(18,6),
    close           NUMERIC(18,6),
    adj_close       NUMERIC(18,6),
    volume          BIGINT,
    source          VARCHAR(32)  NOT NULL DEFAULT 'yfinance',
    ingested_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_date ON ohlcv (ticker, date DESC);

-- Raw news articles (body stored in S3; headline + metadata here)
CREATE TABLE IF NOT EXISTS news_articles (
    id              BIGSERIAL    PRIMARY KEY,
    ticker          VARCHAR(16)  REFERENCES stocks(ticker),
    headline        TEXT         NOT NULL,
    url             TEXT,
    source          VARCHAR(128),
    author          VARCHAR(128),
    published_at    TIMESTAMPTZ,
    s3_path         TEXT,                    -- full body lives in S3
    ingested_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_ticker      ON news_articles (ticker);
CREATE INDEX IF NOT EXISTS idx_news_published   ON news_articles (published_at DESC);

-- SEC filings (10-K, 10-Q)
CREATE TABLE IF NOT EXISTS filings (
    id              BIGSERIAL    PRIMARY KEY,
    ticker          VARCHAR(16)  NOT NULL REFERENCES stocks(ticker),
    cik             VARCHAR(16),             -- SEC CIK identifier
    type            VARCHAR(16)  NOT NULL,   -- '10-K', '10-Q', etc.
    period          DATE,                    -- fiscal period end date
    filed_at        DATE,
    accession_number VARCHAR(32) UNIQUE,
    s3_path         TEXT,                    -- raw filing in S3
    parsed_mda      TEXT,                    -- extracted MD&A text
    ingested_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_filings_ticker ON filings (ticker);
CREATE INDEX IF NOT EXISTS idx_filings_period ON filings (ticker, period DESC);

-- Sentiment scores (linked to news articles or filings)
CREATE TABLE IF NOT EXISTS sentiment_scores (
    id              BIGSERIAL    PRIMARY KEY,
    article_id      BIGINT       REFERENCES news_articles(id),
    filing_id       BIGINT       REFERENCES filings(id),
    ticker          VARCHAR(16)  NOT NULL REFERENCES stocks(ticker),
    score           NUMERIC(6,4),            -- e.g. -1.0 to 1.0
    label           VARCHAR(16),             -- 'positive','negative','neutral'
    model_version   VARCHAR(64),
    scored_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CHECK (article_id IS NOT NULL OR filing_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_sentiment_ticker ON sentiment_scores (ticker);

-- Model predictions
CREATE TABLE IF NOT EXISTS predictions (
    id              BIGSERIAL    PRIMARY KEY,
    ticker          VARCHAR(16)  NOT NULL REFERENCES stocks(ticker),
    model_version   VARCHAR(64)  NOT NULL,
    predicted_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    horizon         INTEGER      NOT NULL,   -- days ahead (e.g. 1, 5, 20)
    predicted_close NUMERIC(18,6),
    confidence      NUMERIC(6,4),            -- 0.0 to 1.0
    features_s3     TEXT                     -- feature vector snapshot in S3
);

CREATE INDEX IF NOT EXISTS idx_predictions_ticker ON predictions (ticker, predicted_at DESC);
