from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from integrations.cloud_sync import CloudSyncClient


def load_env_file(file_name: str = ".env") -> None:
    env_path = Path(file_name)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FarmEase cloud sync worker")
    parser.add_argument("--once", action="store_true", default=False)
    parser.add_argument("--poll-seconds", type=int, default=int(os.getenv("FARMEASE_CLOUD_POLL_SECONDS", "8")))
    parser.add_argument("--event-log", default="data/event_timeline.csv")
    parser.add_argument("--state-path", default="data/.cloud_sync_state.json")
    parser.add_argument("--endpoint", default=os.getenv("FARMEASE_CLOUD_ENDPOINT", ""))
    parser.add_argument("--api-key", default=os.getenv("FARMEASE_CLOUD_API_KEY", ""))
    parser.add_argument("--device-id", default=os.getenv("FARMEASE_DEVICE_ID", "farmease-edge-01"))
    parser.add_argument("--timeout-seconds", type=int, default=int(os.getenv("FARMEASE_CLOUD_TIMEOUT_SECONDS", "8")))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("FARMEASE_CLOUD_BATCH_SIZE", "100")))
    parser.add_argument("--enabled", action="store_true", default=env_bool("FARMEASE_CLOUD_SYNC", default=False))
    return parser.parse_args()


def run_once(client: CloudSyncClient, event_log: str) -> dict[str, object]:
    result = client.sync_once(event_log)
    print(result)
    return result


def main() -> None:
    load_env_file()
    args = parse_args()

    if not args.enabled:
        print("Cloud sync disabled. Set FARMEASE_CLOUD_SYNC=true or pass --enabled.")
        return

    client = CloudSyncClient(
        endpoint=args.endpoint,
        api_key=args.api_key,
        device_id=args.device_id,
        timeout_seconds=args.timeout_seconds,
        batch_size=args.batch_size,
        state_path=args.state_path,
    )

    if args.once:
        run_once(client, args.event_log)
        return

    poll_seconds = max(2, int(args.poll_seconds))
    print(f"Starting cloud sync worker loop (poll every {poll_seconds}s)")
    while True:
        run_once(client, args.event_log)
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
