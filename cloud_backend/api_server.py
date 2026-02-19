from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FarmEase cloud ingest demo API")
    parser.add_argument("--host", default=os.getenv("FARMEASE_CLOUD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("FARMEASE_CLOUD_PORT", "8787")))
    parser.add_argument("--api-key", default=os.getenv("FARMEASE_CLOUD_API_KEY", "demo-key"))
    parser.add_argument("--output", default=os.getenv("FARMEASE_CLOUD_OUTPUT", "data/cloud_ingest.jsonl"))
    return parser.parse_args()


class IngestHandler(BaseHTTPRequestHandler):
    server_version = "FarmEaseCloudAPI/1.0"

    def _json_response(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._json_response(
                200,
                {
                    "ok": True,
                    "service": "farmease-cloud-ingest",
                    "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
            )
            return

        self._json_response(404, {"ok": False, "error": "not-found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/ingest":
            self._json_response(404, {"ok": False, "error": "not-found"})
            return

        expected_key = getattr(self.server, "api_key", "")
        provided_key = self.headers.get("X-API-Key", "")
        if expected_key and provided_key != expected_key:
            self._json_response(401, {"ok": False, "error": "unauthorized"})
            return

        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(content_length) if content_length > 0 else b""
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            self._json_response(400, {"ok": False, "error": "invalid-json"})
            return

        if not isinstance(payload, dict):
            self._json_response(400, {"ok": False, "error": "invalid-payload"})
            return

        events = payload.get("events")
        if not isinstance(events, list):
            self._json_response(400, {"ok": False, "error": "events-must-be-list"})
            return

        record = {
            "received_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "remote_addr": self.client_address[0] if self.client_address else "unknown",
            "payload": payload,
        }

        output_path = Path(getattr(self.server, "output_path", "data/cloud_ingest.jsonl"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(record) + "\n")

        self._json_response(
            200,
            {
                "ok": True,
                "accepted_events": len(events),
                "device_id": payload.get("device_id", "unknown"),
            },
        )

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), IngestHandler)
    server.api_key = args.api_key
    server.output_path = args.output

    print(f"FarmEase cloud ingest API listening on http://{args.host}:{args.port}")
    print(f"Ingest endpoint: http://{args.host}:{args.port}/ingest")
    print(f"Health endpoint: http://{args.host}:{args.port}/health")
    print(f"Output log: {args.output}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
