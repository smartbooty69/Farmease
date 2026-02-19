"""Helpers to push/fetch secrets to/from GCP Secret Manager or env.

This file provides safe, opt-in helpers. It does NOT require cloud libraries
unless you use the GCP functions below. Use environment variables in CI
to avoid storing secrets in the repo.
"""

from typing import Optional
import os


def get_secret_from_env(name: str) -> Optional[str]:
    """Read secret from environment variable `name`."""
    return os.environ.get(name)


def require_env_secret(name: str) -> str:
    v = get_secret_from_env(name)
    if not v:
        raise RuntimeError(f"Secret {name} not set in environment")
    return v


def push_secret_to_gcp(secret_id: str, payload: str, project: str) -> None:
    """Push a secret value to GCP Secret Manager (requires google-cloud-secret-manager).

    This is a convenience helper — run only on a secure machine with gcloud
    auth configured. It will create the secret if it does not exist and add a
    new version.
    """
    try:
        from google.cloud import secretmanager
    except Exception as e:
        raise RuntimeError("google-cloud-secret-manager not installed") from e

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project}"
    name = f"{parent}/secrets/{secret_id}"
    # create secret if missing
    try:
        client.get_secret(request={"name": name})
    except Exception:
        client.create_secret(
            request={"parent": parent, "secret_id": secret_id, "secret": {}}
        )
    # add version
    client.add_secret_version(
        request={"parent": name, "payload": {"data": payload.encode("utf-8")}}
    )


def access_secret_from_gcp(secret_id: str, project: str) -> Optional[str]:
    try:
        from google.cloud import secretmanager
    except Exception as e:
        raise RuntimeError("google-cloud-secret-manager not installed") from e

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project}/secrets/{secret_id}/versions/latest"
    resp = client.access_secret_version(request={"name": name})
    return resp.payload.data.decode("utf-8")
