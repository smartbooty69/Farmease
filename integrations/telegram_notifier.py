from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str | None,
        chat_id: str | None,
        enabled: bool = True,
        default_cooldown_seconds: int = 180,
    ) -> None:
        self.bot_token = (bot_token or "").strip()
        self.chat_id = (chat_id or "").strip()
        self.enabled = enabled and bool(self.bot_token) and bool(self.chat_id)
        self.default_cooldown_seconds = max(10, int(default_cooldown_seconds))
        self.last_sent: dict[str, float] = {}

    def is_configured(self) -> bool:
        return self.enabled

    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

    def _post(
        self, method: str, payload: dict[str, Any], timeout: int = 8
    ) -> tuple[bool, str]:
        if not self.enabled:
            return False, "not-configured"

        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            self._api_url(method),
            data=encoded,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="ignore")
                data = json.loads(body) if body else {}
                ok = bool(data.get("ok"))
                if ok:
                    return True, "ok"
                description = data.get("description", "unknown-error")
                return False, str(description)
        except urllib.error.HTTPError as error:
            return False, f"http-{error.code}"
        except urllib.error.URLError:
            return False, "network-error"
        except Exception:
            return False, "unexpected-error"

    def _get_json(
        self, method: str, params: dict[str, Any], timeout: int = 15
    ) -> tuple[bool, dict[str, Any], str]:
        if not self.enabled:
            return False, {}, "not-configured"

        query = urllib.parse.urlencode(params)
        url = self._api_url(method)
        if query:
            url = f"{url}?{query}"

        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="ignore")
                data = json.loads(body) if body else {}
                ok = bool(data.get("ok"))
                if ok:
                    return True, data, "ok"
                description = data.get("description", "unknown-error")
                return False, data, str(description)
        except urllib.error.HTTPError as error:
            return False, {}, f"http-{error.code}"
        except urllib.error.URLError:
            return False, {}, "network-error"
        except Exception:
            return False, {}, "unexpected-error"

    def send_message(
        self,
        text: str,
        parse_mode: str | None = None,
        disable_notification: bool = False,
        reply_markup: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_notification": disable_notification,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup is not None:
            payload["reply_markup"] = json.dumps(reply_markup)
        return self._post("sendMessage", payload)

    def send_message_async(
        self,
        text: str,
        parse_mode: str | None = None,
        disable_notification: bool = False,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        thread = threading.Thread(
            target=self.send_message,
            args=(text, parse_mode, disable_notification, reply_markup),
            daemon=True,
        )
        thread.start()

    def send_with_cooldown(
        self,
        key: str,
        text: str,
        cooldown_seconds: int | None = None,
        parse_mode: str | None = None,
        disable_notification: bool = False,
    ) -> bool:
        if not self.enabled:
            return False

        now = time.time()
        cooldown = (
            self.default_cooldown_seconds
            if cooldown_seconds is None
            else max(5, int(cooldown_seconds))
        )
        last_time = self.last_sent.get(key, 0.0)

        if (now - last_time) < cooldown:
            return False

        self.last_sent[key] = now
        self.send_message_async(
            text, parse_mode=parse_mode, disable_notification=disable_notification
        )
        return True

    def get_updates(
        self, offset: int | None = None, timeout_seconds: int = 15
    ) -> tuple[bool, list[dict[str, Any]], str]:
        params: dict[str, Any] = {
            "timeout": max(1, int(timeout_seconds)),
            "allowed_updates": json.dumps(["message", "edited_message"]),
        }
        if offset is not None:
            params["offset"] = int(offset)

        ok, data, status = self._get_json(
            "getUpdates", params, timeout=max(5, int(timeout_seconds) + 5)
        )
        if not ok:
            return False, [], status

        result = data.get("result")
        if isinstance(result, list):
            return True, result, "ok"
        return True, [], "ok"
