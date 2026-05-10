"""
Feature engineering pipeline.

Execution order:
  1. technical  — compute indicators for all tickers → technical_features
  2. fundamental — pull ratios from yfinance → fundamental_features
  3. analytics   — rollup sector metrics → sector_analytics

Each stage is independently re-runnable (all upserts are idempotent).

Usage:
    # Full backfill (slow, pulls all OHLCV from DB)
    python -m features.pipeline --mode full

    # Incremental (only yesterday's data, used by the daily DAG)
    python -m features.pipeline --mode incremental
"""
import argparse
import logging
from datetime import date, timedelta

from config.settings import ALL_TICKERS, OHLCV_START_DATE
from data.storage.db_client import (
    load_ohlcv_all,
    upsert_technical_features,
    upsert_fundamental_features,
)
from features import technical, fundamental, analytics

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage 1 — Technical indicators
# ---------------------------------------------------------------------------

def run_technical(start: str | None = None) -> int:
    """Compute and store technical indicators for all tickers."""
    logger.info("Stage 1: Technical indicators (start=%s)", start or "all")
    ohlcv = load_ohlcv_all(start=start)
    if ohlcv.empty:
        logger.warning("No OHLCV data found. Run the price backfill first.")
        return 0

    features_df = technical.compute_batch(ohlcv)
    if features_df.empty:
        return 0

    # Convert DataFrame rows → list of dicts, coercing NaN → None
    records = _df_to_records(features_df, [
        "ticker", "date",
        "sma_20", "sma_50", "sma_200",
        "ema_20", "ema_50", "ema_200",
        "rsi_14", "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_mid", "bb_lower", "bb_pct", "atr_14",
        "obv", "volume_zscore",
        "daily_return", "log_return", "rolling_vol_20",
    ])

    inserted = upsert_technical_features(records)
    logger.info("Stage 1 complete: %d technical feature rows upserted", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Stage 2 — Fundamental features
# ---------------------------------------------------------------------------

def run_fundamental(tickers: list[str] | None = None) -> int:
    """Fetch and store fundamental features from yfinance."""
    tickers = tickers or ALL_TICKERS
    logger.info("Stage 2: Fundamental features for %d tickers", len(tickers))

    records = fundamental.compute_batch(tickers)
    if not records:
        return 0

    inserted = upsert_fundamental_features(records)
    logger.info("Stage 2 complete: %d fundamental rows upserted", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Stage 3 — Sector analytics
# ---------------------------------------------------------------------------

def run_analytics(lookback_days: int = 252) -> int:
    """Compute and store sector-level analytics."""
    logger.info("Stage 3: Sector analytics (lookback=%d days)", lookback_days)
    inserted = analytics.compute_all(lookback_days=lookback_days)
    logger.info("Stage 3 complete: %d sector analytics rows upserted", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Public entrypoints
# ---------------------------------------------------------------------------

def run_full() -> dict:
    """Full backfill — pulls all OHLCV from DB start date."""
    t = run_technical(start=OHLCV_START_DATE)
    f = run_fundamental()
    a = run_analytics(lookback_days=1000)
    return {"technical": t, "fundamental": f, "analytics": a}


def run_incremental() -> dict:
    """
    Incremental update — processes the last 210 trading days of price data
    (enough for SMA-200 warm-up) but only upserts recent rows.
    Fundamental features are refreshed for all tickers (yfinance info is cheap).
    """
    lookback_start = (date.today() - timedelta(days=300)).isoformat()
    t = run_technical(start=lookback_start)
    f = run_fundamental()
    a = run_analytics(lookback_days=252)
    return {"technical": t, "fundamental": f, "analytics": a}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df_to_records(df, columns: list[str]) -> list[dict]:
    """Convert a DataFrame to a list of dicts, keeping only `columns`, NaN → None."""
    import numpy as np
    available = [c for c in columns if c in df.columns]
    sub = df[available].copy()
    # Convert OBV nullable int to regular int/None
    if "obv" in sub.columns:
        sub["obv"] = sub["obv"].apply(
            lambda x: int(x) if (x is not None and x == x and x != float("inf") and x != float("-inf")) else None
        )

    records = sub.to_dict(orient="records")
    # Replace NaN with None (JSON/psycopg2 safe)
    cleaned = [
        {k: (None if isinstance(v, float) and (v != v or abs(v) == float("inf")) else v)
         for k, v in row.items()}
        for row in records
    ]
    return cleaned


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Feature engineering pipeline")
    parser.add_argument(
        "--mode", choices=["full", "incremental"], default="incremental",
        help="'full' = backfill everything; 'incremental' = last 300 days"
    )
    parser.add_argument(
        "--stage", choices=["technical", "fundamental", "analytics", "all"], default="all",
    )
    args = parser.parse_args()

    if args.mode == "full":
        if args.stage == "technical":  run_technical()
        elif args.stage == "fundamental": run_fundamental()
        elif args.stage == "analytics":   run_analytics(lookback_days=1000)
        else: run_full()
    else:
        if args.stage == "technical":  run_technical(start=(date.today() - timedelta(days=300)).isoformat())
        elif args.stage == "fundamental": run_fundamental()
        elif args.stage == "analytics":   run_analytics()
        else: run_incremental()
