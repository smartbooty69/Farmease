from __future__ import annotations

import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class CloudSyncClient:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        device_id: str,
        timeout_seconds: int = 8,
        batch_size: int = 100,
        state_path: str | Path = "data/.cloud_sync_state.json",
    ) -> None:
        self.endpoint = (endpoint or "").strip()
        self.api_key = (api_key or "").strip()
        self.device_id = (device_id or "").strip() or "farmease-edge"
        self.timeout_seconds = max(2, int(timeout_seconds))
        self.batch_size = max(1, int(batch_size))
        self.state_path = Path(state_path)

    def is_configured(self) -> bool:
        return bool(self.endpoint)

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"last_synced_row": 0, "last_sync_epoch": None}

        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return {
                    "last_synced_row": int(payload.get("last_synced_row", 0) or 0),
                    "last_sync_epoch": payload.get("last_sync_epoch"),
                }
        except Exception:
            pass

        return {"last_synced_row": 0, "last_sync_epoch": None}

    def _save_state(self, last_synced_row: int) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_synced_row": int(max(0, last_synced_row)),
            "last_sync_epoch": int(time.time()),
        }
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read_rows(self, csv_path: Path) -> list[dict[str, Any]]:
        if not csv_path.exists():
            return []

        with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            return [dict(row) for row in reader]

    def _build_payload(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "batch_size": len(events),
            "events": events,
            "sent_at_epoch": int(time.time()),
        }

    def _post_json(self, payload: dict[str, Any]) -> tuple[bool, int, str]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                status_code = int(getattr(response, "status", 200) or 200)
                if 200 <= status_code < 300:
                    return True, status_code, "ok"
                return False, status_code, f"http-{status_code}"
        except urllib.error.HTTPError as error:
            return False, int(error.code), f"http-{error.code}"
        except urllib.error.URLError:
            return False, 0, "network-error"
        except Exception:
            return False, 0, "unexpected-error"

    def sync_once(self, event_csv_path: str | Path) -> dict[str, Any]:
        if not self.is_configured():
            return {
                "ok": False,
                "status": "not-configured",
                "synced": 0,
                "pending": 0,
            }

        csv_path = Path(event_csv_path)
        rows = self._read_rows(csv_path)
        state = self._load_state()
        last_synced_row = int(state.get("last_synced_row", 0) or 0)

        if last_synced_row >= len(rows):
            return {
                "ok": True,
                "status": "up-to-date",
                "synced": 0,
                "pending": 0,
            }

        pending = rows[last_synced_row:]
        batch = pending[: self.batch_size]
        payload = self._build_payload(batch)

        ok, http_status, status = self._post_json(payload)
        if not ok:
            return {
                "ok": False,
                "status": status,
                "http_status": http_status,
                "synced": 0,
                "pending": len(pending),
            }

        updated_row = last_synced_row + len(batch)
        self._save_state(updated_row)

        return {
            "ok": True,
            "status": "ok",
            "http_status": http_status,
            "synced": len(batch),
            "pending": max(0, len(rows) - updated_row),
            "last_synced_row": updated_row,
        }
