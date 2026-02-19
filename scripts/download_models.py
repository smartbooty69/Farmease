"""Download model artifacts from cloud storage (GCS or S3) into `models/`.

Usage: set `CLOUD_PROVIDER` and `MODEL_BUCKET` environment variables.
"""

import os
import argparse


def _gcs_download(bucket_name: str, dest_dir: str):
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    for blob in client.list_blobs(bucket_name):
        dest = os.path.join(dest_dir, blob.name)
        print(f"Downloading gs://{bucket_name}/{blob.name} -> {dest}")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        blob.download_to_filename(dest)


def _s3_download(bucket_name: str, dest_dir: str):
    import boto3

    s3 = boto3.client("s3")
    resp = s3.list_objects_v2(Bucket=bucket_name)
    for obj in resp.get("Contents", []):
        key = obj["Key"]
        dest = os.path.join(dest_dir, key)
        print(f"Downloading s3://{bucket_name}/{key} -> {dest}")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        s3.download_file(bucket_name, key, dest)


def main():
    provider = os.environ.get("CLOUD_PROVIDER")
    bucket = os.environ.get("MODEL_BUCKET")
    dest = os.environ.get("MODEL_DEST", "models")
    if not provider or not bucket:
        raise RuntimeError("Set CLOUD_PROVIDER and MODEL_BUCKET environment variables")

    if provider.lower() == "gcs":
        _gcs_download(bucket, dest)
    elif provider.lower() == "s3":
        _s3_download(bucket, dest)
    else:
        raise RuntimeError("Unsupported CLOUD_PROVIDER; use gcs or s3")


if __name__ == "__main__":
    main()
