from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from integrations.cloud_sync import CloudSyncClient
except ImportError:
    import sys

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from integrations.cloud_sync import CloudSyncClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
STATE_FILE = DATA_DIR / ".cloud_sync_state.json"

TRAINING_DATA_FILE = DATA_DIR / "greenhouse_training_data.csv"
EVENT_TIMELINE_FILE = DATA_DIR / "event_timeline.csv"


def load_env_file(file_name: str = ".env") -> None:
    env_path = PROJECT_ROOT / file_name
    if not env_path.exists():
        return

    try:
        with env_path.open("r", encoding="utf-8") as env_file:
            for line in env_file:
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, value = raw.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def read_csv_rows(file_path: Path) -> list[dict[str, str]]:
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def load_state() -> dict[str, int]:
    if not STATE_FILE.exists():
        return {"training_index": 0, "event_index": 0}

    try:
        with STATE_FILE.open("r", encoding="utf-8") as source:
            data = json.load(source)
            return {
                "training_index": int(data.get("training_index", 0)),
                "event_index": int(data.get("event_index", 0)),
            }
    except Exception:
        return {"training_index": 0, "event_index": 0}


def save_state(state: dict[str, int]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as destination:
        json.dump(state, destination, indent=2)


@dataclass
class WorkerConfig:
    poll_seconds: int
    batch_size: int


def read_config() -> WorkerConfig:
    poll_seconds = max(2, int(os.getenv("FARMEASE_CLOUD_POLL_SECONDS", "8")))
    batch_size = max(1, int(os.getenv("FARMEASE_CLOUD_BATCH_SIZE", "100")))
    return WorkerConfig(poll_seconds=poll_seconds, batch_size=batch_size)


def build_payload(source_name: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "source": source_name,
        "rows": rows,
        "row_count": len(rows),
        "device": os.getenv("FARMEASE_DEVICE_ID", "farmease-edge-01"),
        "generated_at": int(time.time()),
    }


def send_new_rows(
    client: CloudSyncClient,
    source_name: str,
    all_rows: list[dict[str, str]],
    start_index: int,
    batch_size: int,
) -> tuple[int, bool]:
    if start_index >= len(all_rows):
        return start_index, True

    chunk = all_rows[start_index : start_index + batch_size]
    payload = build_payload(source_name, chunk)
    ok, status = client.send(payload)

    if not ok:
        print(f"[{source_name}] sync failed: {status}")
        return start_index, False

    next_index = start_index + len(chunk)
    print(f"[{source_name}] synced {len(chunk)} row(s), next index={next_index}")
    return next_index, True


def main() -> None:
    load_env_file()

    enabled = env_bool("FARMEASE_CLOUD_SYNC", default=False)
    endpoint = os.getenv("FARMEASE_CLOUD_ENDPOINT", "")
    api_key = os.getenv("FARMEASE_CLOUD_API_KEY", "")
    timeout_seconds = int(os.getenv("FARMEASE_CLOUD_TIMEOUT_SECONDS", "8"))

    client = CloudSyncClient(
        endpoint=endpoint,
        api_key=api_key,
        enabled=enabled,
        timeout_seconds=timeout_seconds,
    )

    if not client.is_configured():
        print("Cloud sync is disabled or not configured. Set FARMEASE_CLOUD_SYNC=true and FARMEASE_CLOUD_ENDPOINT.")
        return

    config = read_config()
    state = load_state()

    print("FarmEase cloud sync worker started")
    print(f"Endpoint: {endpoint}")
    print(f"Poll interval: {config.poll_seconds}s | Batch size: {config.batch_size}")

    while True:
        training_rows = read_csv_rows(TRAINING_DATA_FILE)
        event_rows = read_csv_rows(EVENT_TIMELINE_FILE)

        next_training, ok_training = send_new_rows(
            client,
            "training_data",
            training_rows,
            state.get("training_index", 0),
            config.batch_size,
        )

        next_event, ok_event = send_new_rows(
            client,
            "event_timeline",
            event_rows,
            state.get("event_index", 0),
            config.batch_size,
        )

        if ok_training:
            state["training_index"] = next_training
        if ok_event:
            state["event_index"] = next_event

        save_state(state)
        time.sleep(config.poll_seconds)


if __name__ == "__main__":
    main()
