"""Upload model artifacts to cloud storage (GCS or S3).

Usage:
  Set environment variables to choose provider and bucket:
    CLOUD_PROVIDER=gcs|s3
    MODEL_BUCKET=your-bucket-name
    (For GCS: GOOGLE_APPLICATION_CREDENTIALS must be set)

This script is intentionally minimal and safe — it will only upload files
from `models/` matching common model extensions.
"""

import os
import glob
import argparse

MODEL_PATTERNS = ["models/*.joblib", "models/*.pkl", "models/*.onnx", "models/*.h5"]


def _gcs_upload(bucket_name: str, sources):
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    for src in sources:
        blob = bucket.blob(os.path.basename(src))
        print(f"Uploading {src} -> gs://{bucket_name}/{blob.name}")
        blob.upload_from_filename(src)


def _s3_upload(bucket_name: str, sources):
    import boto3

    s3 = boto3.client("s3")
    for src in sources:
        key = os.path.basename(src)
        print(f"Uploading {src} -> s3://{bucket_name}/{key}")
        s3.upload_file(src, bucket_name, key)


def main(dry_run: bool = False):
    provider = os.environ.get("CLOUD_PROVIDER")
    bucket = os.environ.get("MODEL_BUCKET")
    if not provider or not bucket:
        raise RuntimeError("Set CLOUD_PROVIDER and MODEL_BUCKET environment variables")

    files = []
    for p in MODEL_PATTERNS:
        files.extend(glob.glob(p))
    if not files:
        print("No model files matched; nothing to upload")
        return

    if dry_run:
        for f in files:
            print("DRY:", f)
        return

    if provider.lower() == "gcs":
        _gcs_upload(bucket, files)
    elif provider.lower() == "s3":
        _s3_upload(bucket, files)
    else:
        raise RuntimeError("Unsupported CLOUD_PROVIDER; use gcs or s3")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
