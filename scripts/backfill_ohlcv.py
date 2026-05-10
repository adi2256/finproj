"""
One-time backfill script: pulls 2+ years of OHLCV for the full universe.
Run this once after standing up the database.

Usage:
    python scripts/backfill_ohlcv.py [--start 2022-01-01] [--end 2024-12-31]
"""
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.ingestion.price_data import run

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end",   default=None)
    args = parser.parse_args()

    inserted = run(start_date=args.start, end_date=args.end)
    print(f"\nBackfill complete: {inserted} rows inserted.")
