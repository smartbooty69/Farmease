import unittest
from unittest.mock import patch

from integrations.telegram_notifier import TelegramNotifier


class TelegramNotifierTests(unittest.TestCase):
    def test_notifier_disabled_without_credentials(self):
        notifier = TelegramNotifier(bot_token="", chat_id="", enabled=True)
        self.assertFalse(notifier.is_configured())

    def test_send_message_builds_payload(self):
        notifier = TelegramNotifier(bot_token="token", chat_id="123", enabled=True)

        captured = {}

        def fake_post(method, payload, timeout=8):
            captured["method"] = method
            captured["payload"] = payload
            captured["timeout"] = timeout
            return True, "ok"

        notifier._post = fake_post

        ok, status = notifier.send_message(
            text="hello",
            parse_mode="Markdown",
            disable_notification=True,
            reply_markup={"keyboard": [["/status"]], "resize_keyboard": True},
        )

        self.assertTrue(ok)
        self.assertEqual(status, "ok")
        self.assertEqual(captured["method"], "sendMessage")
        self.assertEqual(captured["payload"]["chat_id"], "123")
        self.assertEqual(captured["payload"]["text"], "hello")
        self.assertEqual(captured["payload"]["parse_mode"], "Markdown")
        self.assertTrue(captured["payload"]["disable_notification"])
        self.assertIn("reply_markup", captured["payload"])

    def test_send_with_cooldown_blocks_until_elapsed(self):
        notifier = TelegramNotifier(bot_token="token", chat_id="123", enabled=True, default_cooldown_seconds=60)
        notifier.send_message_async = lambda *args, **kwargs: None

        with patch("integrations.telegram_notifier.time.time", side_effect=[1000.0, 1010.0, 1071.0]):
            first = notifier.send_with_cooldown(key="flame", text="alert")
            second = notifier.send_with_cooldown(key="flame", text="alert")
            third = notifier.send_with_cooldown(key="flame", text="alert")

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertTrue(third)

    def test_get_updates_returns_result_list(self):
        notifier = TelegramNotifier(bot_token="token", chat_id="123", enabled=True)

        def fake_get_json(method, params, timeout=15):
            return True, {"ok": True, "result": [{"update_id": 10}]}, "ok"

        notifier._get_json = fake_get_json
        ok, updates, status = notifier.get_updates(offset=11, timeout_seconds=3)

        self.assertTrue(ok)
        self.assertEqual(status, "ok")
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["update_id"], 10)

    def test_get_updates_handles_error(self):
        notifier = TelegramNotifier(bot_token="token", chat_id="123", enabled=True)

        def fake_get_json(method, params, timeout=15):
            return False, {}, "network-error"

        notifier._get_json = fake_get_json
        ok, updates, status = notifier.get_updates()

        self.assertFalse(ok)
        self.assertEqual(updates, [])
        self.assertEqual(status, "network-error")


if __name__ == "__main__":
    unittest.main()
