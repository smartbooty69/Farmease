import importlib
import sys
import types
import unittest
from unittest.mock import patch


class DummyWidget:
    def __init__(self, *args, **kwargs):
        self._config = {}

    def grid(self, *args, **kwargs):
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def grid_rowconfigure(self, *args, **kwargs):
        return None

    def configure(self, **kwargs):
        self._config.update(kwargs)

    def config(self, **kwargs):
        self.configure(**kwargs)

    def title(self, *args, **kwargs):
        return None

    def geometry(self, *args, **kwargs):
        return None

    def minsize(self, *args, **kwargs):
        return None

    def protocol(self, *args, **kwargs):
        return None

    def destroy(self):
        return None

    def mainloop(self):
        return None


class DummyVar:
    def __init__(self, value=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def trace_add(self, *args, **kwargs):
        return None


class DummyScale(DummyWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._value = 0

    def set(self, value):
        self._value = value

    def get(self):
        return self._value


class DummyStyle:
    def __init__(self, *args, **kwargs):
        pass

    def theme_use(self, *args, **kwargs):
        return None

    def configure(self, *args, **kwargs):
        return None


class DummyThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.daemon = daemon

    def start(self):
        return None


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.writes = []

    def readline(self):
        return b""

    def write(self, payload):
        self.writes.append(payload)

    def flush(self):
        return None

    def close(self):
        return None


def build_fake_tk_modules():
    tk_module = types.ModuleType("tkinter")
    tk_module.Tk = DummyWidget
    tk_module.Label = DummyWidget
    tk_module.Frame = DummyWidget
    tk_module.LabelFrame = DummyWidget
    tk_module.Button = DummyWidget
    tk_module.Scale = DummyScale
    tk_module.Checkbutton = DummyWidget
    tk_module.BooleanVar = DummyVar
    tk_module.DoubleVar = DummyVar
    tk_module.HORIZONTAL = "horizontal"

    ttk_module = types.ModuleType("tkinter.ttk")
    ttk_module.Style = DummyStyle
    ttk_module.Progressbar = DummyWidget
    tk_module.ttk = ttk_module

    return tk_module, ttk_module


def load_dashboard_module():
    sys.modules.pop("app.dashboard", None)

    tk_module, ttk_module = build_fake_tk_modules()

    serial_module = types.ModuleType("serial")
    serial_module.Serial = FakeSerial
    serial_module.SerialException = Exception

    with patch.dict(
        sys.modules,
        {
            "tkinter": tk_module,
            "tkinter.ttk": ttk_module,
            "serial": serial_module,
        },
    ):
        with patch("threading.Thread", DummyThread):
            return importlib.import_module("app.dashboard")


class DashboardIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dashboard = load_dashboard_module()

    def setUp(self):
        self.dashboard = self.__class__.dashboard

        for key in self.dashboard.training_state:
            self.dashboard.training_state[key] = None

        self.dashboard.automation_on = True
        self.dashboard.ser.writes.clear()

    def test_process_serial_line_updates_dashboard_state(self):
        counters = {"log": 0, "alerts": 0, "advice": 0}

        self.dashboard.maybe_log_training_row = lambda force=False: counters.__setitem__("log", counters["log"] + 1)
        self.dashboard.maybe_send_telegram_alerts = lambda: counters.__setitem__("alerts", counters["alerts"] + 1)
        self.dashboard.update_dashboard_advice = lambda: counters.__setitem__("advice", counters["advice"] + 1)

        lines = [
            "🌡 Temp: 27.5 C",
            "💧 Hum: 61 %",
            "🌱 Soil ADC: 1700",
            "💡 Light: 16",
            "🔥 Flame: 0 👀 IR: 1",
            "RelayStates: 1 0 1 0",
            "Automation: OFF",
        ]

        for line in lines:
            self.dashboard.process_serial_line(line)

        self.assertEqual(self.dashboard.training_state["temp_c"], 27.5)
        self.assertEqual(self.dashboard.training_state["humidity_pct"], 61.0)
        self.assertEqual(self.dashboard.training_state["soil_adc"], 1700.0)
        self.assertEqual(self.dashboard.training_state["light_lux"], 16.0)
        self.assertEqual(self.dashboard.training_state["flame_detected"], 0)
        self.assertEqual(self.dashboard.training_state["ir_detected"], 1)
        self.assertEqual(self.dashboard.training_state["relay_fan"], 1)
        self.assertEqual(self.dashboard.training_state["relay_pump"], 0)
        self.assertEqual(self.dashboard.training_state["relay_light"], 1)
        self.assertEqual(self.dashboard.training_state["relay_buzzer"], 0)
        self.assertEqual(self.dashboard.training_state["automation_on"], 0)
        self.assertFalse(self.dashboard.automation_on)

        self.assertEqual(counters["log"], len(lines))
        self.assertEqual(counters["alerts"], len(lines))
        self.assertEqual(counters["advice"], len(lines))

    def test_process_telegram_updates_dispatches_authorized_command(self):
        class FakeNotifier:
            def __init__(self):
                self.chat_id = "42"
                self.sent = []

            def get_updates(self, offset=None, timeout_seconds=20):
                return True, [
                    {
                        "update_id": 7,
                        "message": {
                            "chat": {"id": "42"},
                            "text": "/fan_on",
                        },
                    }
                ], "ok"

            def send_message_async(self, text, reply_markup=None):
                self.sent.append((text, reply_markup))

        notifier = FakeNotifier()
        self.dashboard.telegram_notifier = notifier

        next_offset, ok = self.dashboard.process_telegram_updates(None)

        self.assertTrue(ok)
        self.assertEqual(next_offset, 8)
        self.assertIn(b"F", self.dashboard.ser.writes)
        self.assertEqual(len(notifier.sent), 1)
        self.assertIn("Fan ON command sent", notifier.sent[0][0])

    def test_process_telegram_updates_ignores_unauthorized_chat(self):
        class FakeNotifier:
            def __init__(self):
                self.chat_id = "42"
                self.sent = []

            def get_updates(self, offset=None, timeout_seconds=20):
                return True, [
                    {
                        "update_id": 99,
                        "message": {
                            "chat": {"id": "100"},
                            "text": "/fan_on",
                        },
                    }
                ], "ok"

            def send_message_async(self, text, reply_markup=None):
                self.sent.append((text, reply_markup))

        notifier = FakeNotifier()
        self.dashboard.telegram_notifier = notifier

        next_offset, ok = self.dashboard.process_telegram_updates(None)

        self.assertTrue(ok)
        self.assertEqual(next_offset, 100)
        self.assertEqual(self.dashboard.ser.writes, [])
        self.assertEqual(notifier.sent, [])


if __name__ == "__main__":
    unittest.main()
