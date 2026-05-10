"""
OHLCV ingestion via yfinance.
Pulls daily price data for all tickers in the universe and upserts into PostgreSQL.
"""
import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import ALL_TICKERS, OHLCV_START_DATE, SECTORS
from data.storage.db_client import upsert_ohlcv, upsert_stocks

logger = logging.getLogger(__name__)

# yfinance rate-limits aggressively — chunk downloads
BATCH_SIZE = 20


def run(start_date: str = OHLCV_START_DATE, end_date: str | None = None) -> int:
    """
    Pull OHLCV for the full universe from start_date to end_date (defaults to today).
    Returns total rows inserted.
    """
    if end_date is None:
        end_date = date.today().isoformat()

    logger.info("Fetching OHLCV %s → %s for %d tickers", start_date, end_date, len(ALL_TICKERS))

    _seed_stock_metadata()

    total = 0
    for i in range(0, len(ALL_TICKERS), BATCH_SIZE):
        batch = ALL_TICKERS[i : i + BATCH_SIZE]
        total += _fetch_and_store_batch(batch, start_date, end_date)

    logger.info("OHLCV ingest complete — %d rows inserted", total)
    return total


def run_incremental() -> int:
    """Pull only yesterday's close (used by the daily DAG)."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return run(start_date=yesterday, end_date=date.today().isoformat())


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_and_store_batch(tickers: list[str], start: str, end: str) -> int:
    ticker_str = " ".join(tickers)
    df = yf.download(
        ticker_str,
        start=start,
        end=end,
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    records = []
    for ticker in tickers:
        try:
            sub = df[ticker] if len(tickers) > 1 else df
            sub = sub.dropna(subset=["Close"])
        except KeyError:
            logger.warning("No data for %s", ticker)
            continue

        for row_date, row in sub.iterrows():
            records.append({
                "ticker":    ticker,
                "date":      row_date.date(),
                "open":      float(row["Open"]),
                "high":      float(row["High"]),
                "low":       float(row["Low"]),
                "close":     float(row["Close"]),
                "adj_close": float(row["Adj Close"]),
                "volume":    int(row["Volume"]),
                "source":    "yfinance",
            })

    inserted = upsert_ohlcv(records)
    logger.info("Batch %s: %d/%d rows inserted", tickers[0], inserted, len(records))
    return inserted


def _seed_stock_metadata() -> None:
    """Populate stocks table with sector info from our universe definition."""
    records = []
    for sector, tickers in SECTORS.items():
        for ticker in tickers:
            records.append({
                "ticker":     ticker,
                "name":       None,
                "sector":     sector,
                "market_cap": None,
                "exchange":   None,
            })
    upsert_stocks(records)
    logger.info("Seeded %d stock metadata rows", len(records))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
