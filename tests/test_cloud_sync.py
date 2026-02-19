import json
import tempfile
import unittest
from pathlib import Path

from integrations.cloud_sync import CloudSyncClient


class CloudSyncClientTests(unittest.TestCase):
    def test_sync_once_updates_state_on_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            csv_path = temp_root / "event_timeline.csv"
            state_path = temp_root / ".cloud_sync_state.json"

            csv_path.write_text(
                "timestamp,event_type,severity,source,message\n"
                "2026-02-20T10:00:00,alert,warning,automation,Dry soil\n"
                "2026-02-20T10:01:00,control,info,command,Fan ON\n",
                encoding="utf-8",
            )

            client = CloudSyncClient(
                endpoint="http://127.0.0.1:8787/ingest",
                api_key="demo-key",
                device_id="test-device",
                state_path=state_path,
            )
            client._post_json = lambda payload: (True, 200, "ok")

            result = client.sync_once(csv_path)
            self.assertTrue(result["ok"])
            self.assertEqual(result["synced"], 2)
            self.assertEqual(result["pending"], 0)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["last_synced_row"], 2)

    def test_sync_once_returns_not_configured_without_endpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            csv_path = temp_root / "event_timeline.csv"
            csv_path.write_text(
                "timestamp,event_type,severity,source,message\n",
                encoding="utf-8",
            )

            client = CloudSyncClient(
                endpoint="",
                api_key="",
                device_id="test-device",
                state_path=temp_root / ".state.json",
            )

            result = client.sync_once(csv_path)
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "not-configured")


if __name__ == "__main__":
    unittest.main()
