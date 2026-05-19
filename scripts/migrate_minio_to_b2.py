"""
Migrate all objects from MinIO to Backblaze B2.

Usage:
    python scripts/migrate_minio_to_b2.py [--dry-run] [--prefix raw/news/]

Copies every object in the MinIO bucket to the B2 bucket, preserving keys.
After migration, run the SQL migration (003_update_s3_paths.sql) to update
stored paths in PostgreSQL if the bucket name changed.

Requires both sets of credentials in .env:
    MINIO_ENDPOINT, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD  (source)
    B2_ENDPOINT, B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY (destination)
"""
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import boto3

from config.settings import (
    B2_APPLICATION_KEY,
    B2_APPLICATION_KEY_ID,
    B2_ENDPOINT,
    MINIO_ENDPOINT,
    MINIO_ROOT_USER,
    MINIO_ROOT_PASSWORD,
    AWS_REGION,
    S3_BUCKET,
)

logger = logging.getLogger(__name__)


def get_minio_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ROOT_USER,
        aws_secret_access_key=MINIO_ROOT_PASSWORD,
        region_name=AWS_REGION,
    )


def get_b2_client():
    if not B2_ENDPOINT or not B2_APPLICATION_KEY_ID:
        raise ValueError("B2 credentials not configured — set B2_ENDPOINT, B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY in .env")
    return boto3.client(
        "s3",
        endpoint_url=B2_ENDPOINT,
        aws_access_key_id=B2_APPLICATION_KEY_ID,
        aws_secret_access_key=B2_APPLICATION_KEY,
        region_name=AWS_REGION,
    )


def list_all_keys(client, bucket: str, prefix: str = "") -> list[str]:
    keys = []
    paginator = client.get_paginator("list_objects_v2")
    kwargs = {"Bucket": bucket}
    if prefix:
        kwargs["Prefix"] = prefix
    for page in paginator.paginate(**kwargs):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def migrate(
    source_bucket: str,
    dest_bucket: str,
    prefix: str = "",
    dry_run: bool = False,
):
    minio = get_minio_client()
    b2 = get_b2_client()

    keys = list_all_keys(minio, source_bucket, prefix)
    logger.info("Found %d objects in MinIO bucket '%s' (prefix='%s')", len(keys), source_bucket, prefix)

    if not keys:
        logger.info("Nothing to migrate")
        return

    copied = 0
    skipped = 0
    errors = 0

    for key in keys:
        if dry_run:
            logger.info("[DRY RUN] Would copy: %s", key)
            copied += 1
            continue

        try:
            obj = minio.get_object(Bucket=source_bucket, Key=key)
            body = obj["Body"].read()
            content_type = obj.get("ContentType", "application/octet-stream")

            b2.put_object(
                Bucket=dest_bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
            )
            copied += 1
            if copied % 100 == 0:
                logger.info("Progress: %d/%d copied", copied, len(keys))
        except Exception as exc:
            logger.error("Failed to copy %s: %s", key, exc)
            errors += 1

    logger.info(
        "Migration complete: %d copied, %d skipped, %d errors (out of %d total)",
        copied, skipped, errors, len(keys),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Migrate objects from MinIO to Backblaze B2")
    parser.add_argument("--source-bucket", default=S3_BUCKET, help="MinIO bucket name (default: from S3_BUCKET env)")
    parser.add_argument("--dest-bucket", default=S3_BUCKET, help="B2 bucket name (default: same as source)")
    parser.add_argument("--prefix", default="", help="Only migrate keys starting with this prefix (e.g. 'raw/news/')")
    parser.add_argument("--dry-run", action="store_true", help="List what would be copied without copying")
    args = parser.parse_args()

    migrate(
        source_bucket=args.source_bucket,
        dest_bucket=args.dest_bucket,
        prefix=args.prefix,
        dry_run=args.dry_run,
    )
