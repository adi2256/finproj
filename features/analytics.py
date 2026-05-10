"""
Sector-level analytics computed daily from the technical_features table.

Metrics produced:
  - avg_return / median_return / return_dispersion  — cross-sectional return distribution
  - rolling_vol_avg   — average 20-day realised vol across tickers in sector
  - max_drawdown      — worst peak-to-trough over rolling 252-day window (sector equal-weight index)
  - vol_anomaly_pct   — fraction of tickers with |volume_zscore| > 2 on that date

These feed the "always-visible" dashboard analytics that are useful before any ML model exists.
"""
import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text

from config.settings import SECTORS
from data.storage.db_client import get_conn, get_engine, upsert_sector_analytics

logger = logging.getLogger(__name__)


def compute_all(lookback_days: int = 252) -> int:
    """
    Recompute sector analytics for the trailing `lookback_days` window.
    Returns total rows upserted.
    """
    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    tf = _load_technical_features(start)
    if tf.empty:
        logger.warning("No technical_features data found — run feature pipeline first")
        return 0

    records = []
    for sector, tickers in SECTORS.items():
        sector_df = tf[tf["ticker"].isin(tickers)]
        if sector_df.empty:
            continue
        sector_records = _compute_sector(sector, sector_df)
        records.extend(sector_records)

    inserted = upsert_sector_analytics(records)
    logger.info("Sector analytics: %d rows upserted", inserted)
    return inserted


def _load_technical_features(start: str) -> pd.DataFrame:
    sql = text("""
        SELECT ticker, date, daily_return, rolling_vol_20, volume_zscore
        FROM technical_features
        WHERE date >= :start
        ORDER BY ticker, date
    """)
    with get_engine().connect() as conn:
        result = conn.execute(sql, {"start": start})
        df = pd.DataFrame(result.fetchall(), columns=list(result.keys()))
    df["date"] = pd.to_datetime(df["date"])
    return df


def _compute_sector(sector: str, df: pd.DataFrame) -> list[dict]:
    """Compute all analytics for a sector, returning one dict per date."""
    records = []

    # Build equal-weight sector price index for drawdown
    # Use daily_return: equal-weight average
    pivot = df.pivot_table(index="date", columns="ticker", values="daily_return")
    sector_return = pivot.mean(axis=1)          # equal-weight daily return
    vol_pivot     = df.pivot_table(index="date", columns="ticker", values="rolling_vol_20")
    zscore_pivot  = df.pivot_table(index="date", columns="ticker", values="volume_zscore")

    # Compute rolling max-drawdown on the sector index
    cum_index   = (1 + sector_return.fillna(0)).cumprod()
    rolling_max = cum_index.cummax()
    drawdown    = (cum_index - rolling_max) / rolling_max

    for dt in pivot.index:
        day_returns  = pivot.loc[dt].dropna()
        day_vol      = vol_pivot.loc[dt].dropna() if dt in vol_pivot.index else pd.Series(dtype=float)
        day_zscore   = zscore_pivot.loc[dt].dropna() if dt in zscore_pivot.index else pd.Series(dtype=float)

        vol_anomaly_pct = (
            (day_zscore.abs() > 2).mean() * 100
            if len(day_zscore) > 0 else None
        )

        records.append({
            "sector":            sector,
            "date":              dt.date() if hasattr(dt, "date") else dt,
            "avg_return":        _f(day_returns.mean()),
            "median_return":     _f(day_returns.median()),
            "return_dispersion": _f(day_returns.std(ddof=1)),
            "rolling_vol_avg":   _f(day_vol.mean()),
            "max_drawdown":      _f(drawdown.get(dt)),
            "vol_anomaly_pct":   _f(vol_anomaly_pct),
        })

    return records


def compute_correlation_matrix(
    tickers: list[str],
    start: str,
    end: str | None = None,
) -> pd.DataFrame:
    """
    Returns a correlation matrix of daily log-returns for the given tickers.
    Used directly by the dashboard and the EDA notebook.
    """
    sql = text("""
        SELECT ticker, date, log_return
        FROM technical_features
        WHERE ticker = ANY(:tickers)
          AND date >= :start
          {end_clause}
        ORDER BY date
    """.format(end_clause="AND date <= :end" if end else ""))
    params: dict = {"tickers": tickers, "start": start}
    if end:
        params["end"] = end

    with get_conn() as conn:
        df = pd.read_sql(sql, conn, params=params, parse_dates=["date"])

    pivot = df.pivot_table(index="date", columns="ticker", values="log_return")
    return pivot.corr()


def compute_drawdown_series(ticker: str, start: str) -> pd.Series:
    """
    Compute the rolling drawdown series for a single ticker.
    Returns a Series indexed by date.
    """
    sql = text("""
        SELECT date, daily_return FROM technical_features
        WHERE ticker = :ticker AND date >= :start ORDER BY date
    """)
    with get_conn() as conn:
        df = pd.read_sql(sql, conn, params={"ticker": ticker, "start": start},
                         parse_dates=["date"])
    if df.empty:
        return pd.Series(dtype=float)

    df = df.set_index("date")
    cum  = (1 + df["daily_return"].fillna(0)).cumprod()
    peak = cum.cummax()
    return (cum - peak) / peak


def compute_volume_anomalies(
    tickers: list[str],
    start: str,
    zscore_threshold: float = 2.0,
) -> pd.DataFrame:
    """
    Returns rows where a ticker's volume z-score exceeded the threshold.
    Useful for surfacing unusual trading activity on the dashboard.
    """
    sql = text("""
        SELECT t.ticker, t.date, t.volume_zscore, o.volume,
               s.sector
        FROM technical_features t
        JOIN ohlcv o USING (ticker, date)
        JOIN stocks s USING (ticker)
        WHERE t.ticker = ANY(:tickers)
          AND t.date >= :start
          AND ABS(t.volume_zscore) >= :threshold
        ORDER BY t.date DESC, ABS(t.volume_zscore) DESC
    """)
    with get_conn() as conn:
        df = pd.read_sql(sql, conn, params={
            "tickers":   tickers,
            "start":     start,
            "threshold": zscore_threshold,
        }, parse_dates=["date"])
    return df


def _f(val) -> float | None:
    """Safe float coercion."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if (f != f or abs(f) == float("inf")) else round(f, 6)
    except (TypeError, ValueError):
        return None
