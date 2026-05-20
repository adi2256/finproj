#!/usr/bin/env python3
"""
Delete raw SEC filing blobs from cloud storage once sentiment has been scored.

Sentiment scores live in PostgreSQL — the raw filing text is only needed
while the scoring DAG runs.  After that the blob is dead weight.

Usage:
    # Preview what would be deleted (filings older than 1 year that have scores):
    python scripts/cleanup_old_filings.py --keep-days 365

    # Actually delete:
    python scripts/cleanup_old_filings.py --keep-days 365 --execute

    # Aggressive: keep only 6 months of raw filings:
    python scripts/cleanup_old_filings.py --keep-days 180 --execute
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.storage.s3_client import cleanup_old_filings


def main():
    parser = argparse.ArgumentParser(description="Clean up old filing blobs from cloud storage")
    parser.add_argument(
        "--keep-days", type=int, default=365,
        help="Keep filings newer than this many days (default: 365)",
    )
    parser.add_argument(
        "--include-unscored", action="store_true",
        help="Also delete filings that were never scored (saves more space).",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually delete. Without this flag, runs in dry-run mode.",
    )
    args = parser.parse_args()

    dry_run = not args.execute
    mode = "DRY RUN" if dry_run else "LIVE"
    scope = "all filings" if args.include_unscored else "scored filings only"
    print(f"[{mode}] Cleaning {scope} older than {args.keep_days} days...\n")

    result = cleanup_old_filings(
        keep_days=args.keep_days,
        include_unscored=args.include_unscored,
        dry_run=dry_run,
    )

    freed_mb = result["freed_bytes"] / 1024 ** 2
    print(f"\n{'Would delete' if dry_run else 'Deleted'}: {result['deleted']} filings ({freed_mb:.1f} MB)")
    print(f"Skipped (not yet scored): {result['skipped_unscored']}")

    if dry_run and result["deleted"] > 0:
        print(f"\nRe-run with --execute to actually delete.")


if __name__ == "__main__":
    main()
