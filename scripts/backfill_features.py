"""
One-time full feature backfill.
Run AFTER backfill_ohlcv.py and backfill_filings.py have populated their tables.

Usage:
    python scripts/backfill_features.py                # all stages
    python scripts/backfill_features.py --stage technical
    python scripts/backfill_features.py --stage fundamental
    python scripts/backfill_features.py --stage analytics
"""
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from features.pipeline import run_full, run_technical, run_fundamental, run_analytics

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        choices=["all", "technical", "fundamental", "analytics"],
        default="all",
    )
    args = parser.parse_args()

    if args.stage == "technical":
        n = run_technical()
        print(f"\nDone: {n} technical feature rows.")
    elif args.stage == "fundamental":
        n = run_fundamental()
        print(f"\nDone: {n} fundamental rows.")
    elif args.stage == "analytics":
        n = run_analytics(lookback_days=1000)
        print(f"\nDone: {n} sector analytics rows.")
    else:
        result = run_full()
        print(f"\nFull backfill complete: {result}")
