"""PostgreSQL connection and upsert helpers."""
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config.settings import DATABASE_URL

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        kwargs = dict(pool_pre_ping=True)
        if "neon.tech" in DATABASE_URL or os.getenv("DB_SSL_REQUIRE"):
            kwargs.update(pool_size=3, max_overflow=2)
        _engine = create_engine(DATABASE_URL, **kwargs)
    return _engine


@contextmanager
def get_conn():
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def upsert_ohlcv(records: list[dict]) -> int:
    """Insert OHLCV rows, skipping duplicates. Returns inserted count."""
    if not records:
        return 0

    sql = text("""
        INSERT INTO ohlcv (ticker, date, open, high, low, close, adj_close, volume, source)
        VALUES (:ticker, :date, :open, :high, :low, :close, :adj_close, :volume, :source)
        ON CONFLICT (ticker, date) DO NOTHING
    """)
    with get_conn() as conn:
        result = conn.execute(sql, records)
    return result.rowcount


def upsert_stocks(records: list[dict]) -> None:
    """Insert stock metadata, updating on conflict."""
    if not records:
        return

    sql = text("""
        INSERT INTO stocks (ticker, name, sector, market_cap, exchange)
        VALUES (:ticker, :name, :sector, :market_cap, :exchange)
        ON CONFLICT (ticker) DO UPDATE
            SET name       = EXCLUDED.name,
                sector     = EXCLUDED.sector,
                market_cap = EXCLUDED.market_cap,
                exchange   = EXCLUDED.exchange
    """)
    with get_conn() as conn:
        conn.execute(sql, records)


def insert_news_article(record: dict) -> int:
    """Insert a news article and return its id."""
    sql = text("""
        INSERT INTO news_articles (ticker, headline, url, source, author, published_at, s3_path)
        VALUES (:ticker, :headline, :url, :source, :author, :published_at, :s3_path)
        RETURNING id
    """)
    with get_conn() as conn:
        result = conn.execute(sql, record)
        return result.scalar()


def insert_filing(record: dict) -> int:
    """Insert a filing row (skipping if accession_number already exists). Returns id."""
    sql = text("""
        INSERT INTO filings (ticker, cik, type, period, filed_at, accession_number, s3_path, parsed_mda)
        VALUES (:ticker, :cik, :type, :period, :filed_at, :accession_number, :s3_path, :parsed_mda)
        ON CONFLICT (accession_number) DO NOTHING
        RETURNING id
    """)
    with get_conn() as conn:
        result = conn.execute(sql, record)
        return result.scalar()


# ---------------------------------------------------------------------------
# Phase 2 — Feature tables
# ---------------------------------------------------------------------------

def upsert_technical_features(records: list[dict]) -> int:
    """Upsert technical indicator rows. Updates all columns on conflict."""
    if not records:
        return 0
    sql = text("""
        INSERT INTO technical_features (
            ticker, date,
            sma_20, sma_50, sma_200, ema_20, ema_50, ema_200,
            rsi_14, macd, macd_signal, macd_hist,
            bb_upper, bb_mid, bb_lower, bb_pct, atr_14,
            obv, volume_zscore,
            daily_return, log_return, rolling_vol_20
        ) VALUES (
            :ticker, :date,
            :sma_20, :sma_50, :sma_200, :ema_20, :ema_50, :ema_200,
            :rsi_14, :macd, :macd_signal, :macd_hist,
            :bb_upper, :bb_mid, :bb_lower, :bb_pct, :atr_14,
            :obv, :volume_zscore,
            :daily_return, :log_return, :rolling_vol_20
        )
        ON CONFLICT (ticker, date) DO UPDATE SET
            sma_20        = EXCLUDED.sma_20,
            sma_50        = EXCLUDED.sma_50,
            sma_200       = EXCLUDED.sma_200,
            ema_20        = EXCLUDED.ema_20,
            ema_50        = EXCLUDED.ema_50,
            ema_200       = EXCLUDED.ema_200,
            rsi_14        = EXCLUDED.rsi_14,
            macd          = EXCLUDED.macd,
            macd_signal   = EXCLUDED.macd_signal,
            macd_hist     = EXCLUDED.macd_hist,
            bb_upper      = EXCLUDED.bb_upper,
            bb_mid        = EXCLUDED.bb_mid,
            bb_lower      = EXCLUDED.bb_lower,
            bb_pct        = EXCLUDED.bb_pct,
            atr_14        = EXCLUDED.atr_14,
            obv           = EXCLUDED.obv,
            volume_zscore = EXCLUDED.volume_zscore,
            daily_return  = EXCLUDED.daily_return,
            log_return    = EXCLUDED.log_return,
            rolling_vol_20 = EXCLUDED.rolling_vol_20,
            computed_at   = NOW()
    """)
    with get_conn() as conn:
        result = conn.execute(sql, records)
    return result.rowcount


def upsert_fundamental_features(records: list[dict]) -> int:
    """Upsert fundamental feature rows. Updates on conflict."""
    if not records:
        return 0
    sql = text("""
        INSERT INTO fundamental_features (
            ticker, period, filing_id,
            pe_ratio, pb_ratio, ps_ratio, ev_ebitda,
            revenue_qoq, revenue_yoy, earnings_growth,
            gross_margin, operating_margin, net_margin, roe, roa,
            eps_actual, eps_estimate, eps_surprise,
            debt_to_equity, current_ratio, quick_ratio
        ) VALUES (
            :ticker, :period, :filing_id,
            :pe_ratio, :pb_ratio, :ps_ratio, :ev_ebitda,
            :revenue_qoq, :revenue_yoy, :earnings_growth,
            :gross_margin, :operating_margin, :net_margin, :roe, :roa,
            :eps_actual, :eps_estimate, :eps_surprise,
            :debt_to_equity, :current_ratio, :quick_ratio
        )
        ON CONFLICT (ticker, period) DO UPDATE SET
            pe_ratio         = EXCLUDED.pe_ratio,
            pb_ratio         = EXCLUDED.pb_ratio,
            ps_ratio         = EXCLUDED.ps_ratio,
            ev_ebitda        = EXCLUDED.ev_ebitda,
            revenue_qoq      = EXCLUDED.revenue_qoq,
            revenue_yoy      = EXCLUDED.revenue_yoy,
            earnings_growth  = EXCLUDED.earnings_growth,
            gross_margin     = EXCLUDED.gross_margin,
            operating_margin = EXCLUDED.operating_margin,
            net_margin       = EXCLUDED.net_margin,
            roe              = EXCLUDED.roe,
            roa              = EXCLUDED.roa,
            eps_actual       = EXCLUDED.eps_actual,
            eps_estimate     = EXCLUDED.eps_estimate,
            eps_surprise     = EXCLUDED.eps_surprise,
            debt_to_equity   = EXCLUDED.debt_to_equity,
            current_ratio    = EXCLUDED.current_ratio,
            quick_ratio      = EXCLUDED.quick_ratio,
            computed_at      = NOW()
    """)
    with get_conn() as conn:
        result = conn.execute(sql, records)
    return result.rowcount


def upsert_sector_analytics(records: list[dict]) -> int:
    """Upsert sector analytics rows."""
    if not records:
        return 0
    sql = text("""
        INSERT INTO sector_analytics (
            sector, date,
            avg_return, median_return, return_dispersion,
            rolling_vol_avg, max_drawdown, vol_anomaly_pct
        ) VALUES (
            :sector, :date,
            :avg_return, :median_return, :return_dispersion,
            :rolling_vol_avg, :max_drawdown, :vol_anomaly_pct
        )
        ON CONFLICT (sector, date) DO UPDATE SET
            avg_return        = EXCLUDED.avg_return,
            median_return     = EXCLUDED.median_return,
            return_dispersion = EXCLUDED.return_dispersion,
            rolling_vol_avg   = EXCLUDED.rolling_vol_avg,
            max_drawdown      = EXCLUDED.max_drawdown,
            vol_anomaly_pct   = EXCLUDED.vol_anomaly_pct,
            computed_at       = NOW()
    """)
    with get_conn() as conn:
        result = conn.execute(sql, records)
    return result.rowcount


def _query_df(query: str, params: dict | None = None, parse_dates: list[str] | None = None) -> "pd.DataFrame":
    """Execute a SELECT query and return results as a DataFrame (pandas-version-agnostic)."""
    import pandas as pd
    with get_engine().connect() as conn:
        result = conn.execute(text(query), params or {})
        df = pd.DataFrame(result.fetchall(), columns=list(result.keys()))
    if parse_dates:
        for col in parse_dates:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
    return df


def load_ohlcv(ticker: str, start: str | None = None) -> "pd.DataFrame":
    """Load OHLCV for a ticker into a DataFrame, sorted by date."""
    query = "SELECT date, open, high, low, close, adj_close, volume FROM ohlcv WHERE ticker = :ticker"
    params: dict = {"ticker": ticker}
    if start:
        query += " AND date >= :start"
        params["start"] = start
    query += " ORDER BY date ASC"
    df = _query_df(query, params, parse_dates=["date"])
    for col in ["open", "high", "low", "close", "adj_close", "volume"]:
        df[col] = df[col].astype(float)
    return df.set_index("date")


# ---------------------------------------------------------------------------
# Phase 3 — Sentiment helpers
# ---------------------------------------------------------------------------

def insert_sentiment_score(record: dict) -> int:
    """Insert a sentiment score row. Returns id."""
    sql = text("""
        INSERT INTO sentiment_scores (article_id, filing_id, ticker, score, label, model_version)
        VALUES (:article_id, :filing_id, :ticker, :score, :label, :model_version)
        RETURNING id
    """)
    with get_conn() as conn:
        result = conn.execute(sql, record)
        return result.scalar()


def bulk_insert_sentiment_scores(records: list[dict]) -> int:
    """Bulk insert sentiment scores. Returns inserted count."""
    if not records:
        return 0
    sql = text("""
        INSERT INTO sentiment_scores (article_id, filing_id, ticker, score, label, model_version)
        VALUES (:article_id, :filing_id, :ticker, :score, :label, :model_version)
    """)
    with get_conn() as conn:
        result = conn.execute(sql, records)
    return result.rowcount


def upsert_daily_sentiment_agg(records: list[dict]) -> int:
    """Upsert daily sentiment aggregation rows."""
    if not records:
        return 0
    sql = text("""
        INSERT INTO daily_sentiment_agg (
            ticker, date, avg_score, min_score, max_score,
            article_count, positive_pct, negative_pct, neutral_pct
        ) VALUES (
            :ticker, :date, :avg_score, :min_score, :max_score,
            :article_count, :positive_pct, :negative_pct, :neutral_pct
        )
        ON CONFLICT (ticker, date) DO UPDATE SET
            avg_score     = EXCLUDED.avg_score,
            min_score     = EXCLUDED.min_score,
            max_score     = EXCLUDED.max_score,
            article_count = EXCLUDED.article_count,
            positive_pct  = EXCLUDED.positive_pct,
            negative_pct  = EXCLUDED.negative_pct,
            neutral_pct   = EXCLUDED.neutral_pct,
            computed_at   = NOW()
    """)
    with get_conn() as conn:
        result = conn.execute(sql, records)
    return result.rowcount


def upsert_filing_sentiment(record: dict) -> int:
    """Upsert a filing-level sentiment row. Returns id."""
    sql = text("""
        INSERT INTO filing_sentiment (
            filing_id, ticker, period, avg_score, label,
            prev_period_score, score_delta, model_version
        ) VALUES (
            :filing_id, :ticker, :period, :avg_score, :label,
            :prev_period_score, :score_delta, :model_version
        )
        ON CONFLICT (filing_id) DO UPDATE SET
            avg_score         = EXCLUDED.avg_score,
            label             = EXCLUDED.label,
            prev_period_score = EXCLUDED.prev_period_score,
            score_delta       = EXCLUDED.score_delta,
            model_version     = EXCLUDED.model_version,
            computed_at       = NOW()
        RETURNING id
    """)
    with get_conn() as conn:
        result = conn.execute(sql, record)
        return result.scalar()


def load_unscored_articles(limit: int = 5000) -> "pd.DataFrame":
    """Load news articles that don't yet have a sentiment score."""
    sql = """
        SELECT na.id AS article_id, na.ticker, na.headline, na.published_at
        FROM news_articles na
        LEFT JOIN sentiment_scores ss ON ss.article_id = na.id
        WHERE ss.id IS NULL
        ORDER BY na.published_at DESC
        LIMIT :limit
    """
    return _query_df(sql, {"limit": limit}, parse_dates=["published_at"])


def load_unscored_filings() -> "pd.DataFrame":
    """Load filings with MD&A text that haven't been sentiment-scored."""
    sql = """
        SELECT f.id AS filing_id, f.ticker, f.type, f.period, f.parsed_mda
        FROM filings f
        LEFT JOIN filing_sentiment fs ON fs.filing_id = f.id
        WHERE fs.id IS NULL AND f.parsed_mda IS NOT NULL
        ORDER BY f.period DESC
    """
    return _query_df(sql)


def load_daily_sentiment(ticker: str, start: str | None = None) -> "pd.DataFrame":
    """Load daily sentiment aggregation for a ticker."""
    query = "SELECT date, avg_score, article_count FROM daily_sentiment_agg WHERE ticker = :ticker"
    params: dict = {"ticker": ticker}
    if start:
        query += " AND date >= :start"
        params["start"] = start
    query += " ORDER BY date ASC"
    return _query_df(query, params, parse_dates=["date"]).set_index("date")


def load_ohlcv_all(start: str | None = None) -> "pd.DataFrame":
    """Load OHLCV for ALL tickers. Returns a DataFrame with (ticker, date) MultiIndex."""
    query = "SELECT ticker, date, open, high, low, close, adj_close, volume FROM ohlcv"
    params: dict = {}
    if start:
        query += " WHERE date >= :start"
        params["start"] = start
    query += " ORDER BY ticker, date ASC"
    df = _query_df(query, params or None, parse_dates=["date"])
    for col in ["open", "high", "low", "close", "adj_close", "volume"]:
        df[col] = df[col].astype(float)
    return df.set_index(["ticker", "date"])
