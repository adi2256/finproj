"""
One-time backfill: pull historical 10-K/10-Q for the full universe.
Respects SEC rate limits (0.15s delay per request).

Usage:
    python scripts/backfill_filings.py
    python scripts/backfill_filings.py --tickers AAPL MSFT NVDA
"""
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.ingestion.sec_filings import run

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="*", default=None,
                        help="Subset of tickers (default: full universe)")
    args = parser.parse_args()

    stored = run(tickers=args.tickers)
    print(f"\nBackfill complete: {stored} filings stored.")
