from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class CloudSyncClient:
    def __init__(
        self,
        endpoint: str | None,
        api_key: str | None = None,
        enabled: bool = False,
        timeout_seconds: int = 8,
    ) -> None:
        self.endpoint = (endpoint or "").strip()
        self.api_key = (api_key or "").strip()
        self.enabled = bool(enabled) and bool(self.endpoint)
        self.timeout_seconds = max(3, int(timeout_seconds))

    def is_configured(self) -> bool:
        return self.enabled

    def send(self, payload: dict[str, Any]) -> tuple[bool, str]:
        if not self.enabled:
            return False, "not-configured"

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "FarmEase-CloudSync/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers=headers,
        )

        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                if 200 <= int(response.status) < 300:
                    return True, "ok"
                return False, f"http-{response.status}"
        except urllib.error.HTTPError as error:
            return False, f"http-{error.code}"
        except urllib.error.URLError:
            return False, "network-error"
        except Exception:
            return False, "unexpected-error"
