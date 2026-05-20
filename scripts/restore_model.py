"""
Restore a fine-tuned model downloaded from Kaggle into the project.

Usage (after downloading finbert-finetuned-final.zip from Kaggle):
    python scripts/restore_model.py --zip ~/Downloads/finbert-finetuned-final.zip

What it does:
  1. Unzips to ./finbert-finetuned/final/
  2. Optionally uploads to S3/MinIO so the Airflow DAG can load it
"""
import argparse
import json
import os
import shutil
import zipfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DEST  = os.path.join(PROJECT_ROOT, "finbert-finetuned", "final")


def restore(zip_path: str, dest_dir: str, upload: bool) -> None:
    zip_path = os.path.expanduser(zip_path)
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"Zip not found: {zip_path}")

    print(f"Extracting {zip_path} → {dest_dir}")
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)

    # Print training metadata if present
    meta_path = os.path.join(dest_dir, "training_meta.json")
    if os.path.isfile(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        print("\n=== Model info ===")
        for k, v in meta.items():
            print(f"  {k}: {v}")

    print(f"\nModel ready at: {dest_dir}")
    print("Test with:  python -m sentiment.inference")

    if upload:
        import sys
        sys.path.insert(0, PROJECT_ROOT)
        from config.settings import SENTIMENT_MODEL_VERSION
        from data.storage.s3_client import upload_model_dir
        s3_path = upload_model_dir(dest_dir, SENTIMENT_MODEL_VERSION)
        print(f"Uploaded to S3: {s3_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore Kaggle fine-tuned model")
    parser.add_argument("--zip",    required=True, help="Path to finbert-finetuned-final.zip")
    parser.add_argument("--dest",   default=DEFAULT_DEST, help="Local destination directory")
    parser.add_argument("--upload-s3", action="store_true", help="Also upload to S3/MinIO")
    args = parser.parse_args()

    restore(args.zip, args.dest, args.upload_s3)
