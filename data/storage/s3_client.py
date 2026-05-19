"""
Storage abstraction — local filesystem, MinIO, or AWS S3.

The public API is identical for all three backends:
    upload_json(data, prefix_key, filename)  → stored path string
    upload_text(text, prefix_key, filename)  → stored path string
    download_json(stored_path)               → dict

Which backend is used is controlled by STORAGE_BACKEND in your .env:
    local   — writes to ./storage/ on disk. Zero setup, works offline.
    minio   — MinIO container in Docker. S3-compatible, free, has a browser UI.
    s3      — AWS S3. Requires AWS credentials. Used if/when you upgrade.

Stored path formats:
    local   →  local://storage/raw/news/AAPL/2024/01/15/abc.json
    minio   →  s3://finance-data/raw/news/AAPL/2024/01/15/abc.json
    s3      →  s3://your-bucket/raw/news/AAPL/2024/01/15/abc.json

All callers (news_data.py, sec_filings.py, etc.) only call upload_json /
upload_text / download_json — they never see the backend details.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from config.settings import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    B2_APPLICATION_KEY,
    B2_APPLICATION_KEY_ID,
    B2_ENDPOINT,
    MINIO_ENDPOINT,
    S3_BUCKET,
    S3_PREFIXES,
    STORAGE_BACKEND,
    STORAGE_ROOT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------
_s3_client = None


def _get_s3():
    """Return a boto3 client pointed at MinIO, Backblaze B2, or real AWS depending on config."""
    global _s3_client
    if _s3_client is None:
        import boto3
        if STORAGE_BACKEND == "b2":
            kwargs = dict(
                region_name=AWS_REGION,
                aws_access_key_id=B2_APPLICATION_KEY_ID,
                aws_secret_access_key=B2_APPLICATION_KEY,
                endpoint_url=B2_ENDPOINT,
            )
        else:
            kwargs = dict(
                region_name=AWS_REGION,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            )
            if STORAGE_BACKEND == "minio":
                kwargs["endpoint_url"] = MINIO_ENDPOINT
        _s3_client = boto3.client("s3", **kwargs)
    return _s3_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_json(data: dict, prefix_key: str, filename: str) -> str:
    """
    Upload a dict as JSON.
    Returns the stored path (use this as the value saved in the DB).
    """
    prefix = S3_PREFIXES.get(prefix_key, f"raw/{prefix_key}/")
    body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")

    if STORAGE_BACKEND == "local":
        return _local_write(body, prefix, filename)
    else:
        return _s3_put(body, prefix, filename, "application/json")


def upload_text(text: str, prefix_key: str, filename: str) -> str:
    """
    Upload a plain-text string (e.g. raw SEC filing).
    Returns the stored path.
    """
    prefix = S3_PREFIXES.get(prefix_key, f"raw/{prefix_key}/")
    body = text.encode("utf-8")

    if STORAGE_BACKEND == "local":
        return _local_write(body, prefix, filename)
    else:
        return _s3_put(body, prefix, filename, "text/plain")


def download_json(stored_path: str) -> dict:
    """
    Download and parse a JSON file using the stored path returned by upload_json.
    """
    if stored_path.startswith("local://"):
        return _local_read_json(stored_path)
    else:
        return _s3_read_json(stored_path)


# ---------------------------------------------------------------------------
# Filename helpers (unchanged — callers use these directly)
# ---------------------------------------------------------------------------

def news_s3_filename(ticker: str, article_id: str, published_at: datetime) -> str:
    date_str = published_at.strftime("%Y/%m/%d")
    return f"{ticker}/{date_str}/{article_id}.json"


def filing_s3_filename(ticker: str, accession: str, filing_type: str) -> str:
    clean_accession = accession.replace("-", "")
    return f"{ticker}/{filing_type}/{clean_accession}.txt"


# ---------------------------------------------------------------------------
# Phase 3 — Model artifact helpers
# ---------------------------------------------------------------------------

def upload_model_dir(local_dir: str, model_version: str) -> str:
    """Upload all files in a local directory under models/<version>/."""
    import os as _os
    prefix = S3_PREFIXES.get("models", "models/")
    s3_prefix = f"{prefix}{model_version}/"

    if STORAGE_BACKEND == "local":
        # For local backend just record the source path — nothing to copy
        path = f"local://{local_dir}"
        logger.info("Local backend: model stays at %s", local_dir)
        return path

    client = _get_s3()
    for root, _dirs, files in _os.walk(local_dir):
        for fname in files:
            local_path = _os.path.join(root, fname)
            rel_path = _os.path.relpath(local_path, local_dir)
            key = f"{s3_prefix}{rel_path}"
            client.upload_file(local_path, S3_BUCKET, key)
            logger.info("Uploaded %s → s3://%s/%s", rel_path, S3_BUCKET, key)

    s3_path = f"s3://{S3_BUCKET}/{s3_prefix}"
    logger.info("Model upload complete: %s", s3_path)
    return s3_path


def download_model_dir(model_version: str, local_dir: str) -> str:
    """Download a model from storage to a local directory."""
    import os as _os

    if STORAGE_BACKEND == "local":
        logger.info("Local backend: model already at %s", local_dir)
        return local_dir

    prefix = S3_PREFIXES.get("models", "models/")
    s3_prefix = f"{prefix}{model_version}/"
    client = _get_s3()

    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=s3_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            rel_path = key[len(s3_prefix):]
            local_path = _os.path.join(local_dir, rel_path)
            _os.makedirs(_os.path.dirname(local_path), exist_ok=True)
            client.download_file(S3_BUCKET, key, local_path)
            logger.info("Downloaded s3://%s/%s → %s", S3_BUCKET, key, local_path)

    return local_dir


# ---------------------------------------------------------------------------
# Internal — local filesystem backend
# ---------------------------------------------------------------------------

def _local_write(body: bytes, prefix: str, filename: str) -> str:
    full_path = Path(STORAGE_ROOT) / prefix / filename
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(body)
    stored = f"local://{full_path}"
    logger.debug("Stored locally: %s", stored)
    return stored


def _local_read_json(stored_path: str) -> dict:
    file_path = Path(stored_path.removeprefix("local://"))
    return json.loads(file_path.read_bytes())


# ---------------------------------------------------------------------------
# Internal — S3 / MinIO backend (same boto3 code, different endpoint)
# ---------------------------------------------------------------------------

def _s3_put(body: bytes, prefix: str, filename: str, content_type: str) -> str:
    key = f"{prefix}{filename}"
    _get_s3().put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    path = f"s3://{S3_BUCKET}/{key}"
    logger.debug("Uploaded: %s", path)
    return path


def _s3_read_json(stored_path: str) -> dict:
    assert stored_path.startswith("s3://"), f"Unexpected path: {stored_path}"
    parts = stored_path[5:].split("/", 1)
    bucket, key = parts[0], parts[1]
    obj = _get_s3().get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())
