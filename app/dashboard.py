import tkinter as tk
from tkinter import ttk
import serial
import threading
import time
import csv
import os
import re
from collections import deque
from datetime import datetime
from integrations.telegram_notifier import TelegramNotifier

# ---------- SERIAL SETUP ----------
PORT = "COM3"
BAUD = 115200

DATA_DIR = "data"
TRAINING_DATA_FILE = os.path.join(DATA_DIR, "greenhouse_training_data.csv")
LOG_INTERVAL_SECONDS = 2
MODEL_READY_ROWS = 1000


def load_env_file(file_name=".env"):
    if not os.path.exists(file_name):
        return

    try:
        with open(file_name, "r", encoding="utf-8") as env_file:
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


load_env_file()


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ALERTS_ENABLED = env_bool("TELEGRAM_ALERTS", default=False)
TELEGRAM_ALERT_COOLDOWN = int(os.getenv("TELEGRAM_ALERT_COOLDOWN", "180"))
TELEGRAM_ALERT_TEMP_OFFSET = float(os.getenv("TELEGRAM_ALERT_TEMP_OFFSET", "2"))
TELEGRAM_TEMP_FAULT_MIN_C = float(os.getenv("TELEGRAM_TEMP_FAULT_MIN_C", "5"))
TELEGRAM_TEMP_FAULT_MAX_C = float(os.getenv("TELEGRAM_TEMP_FAULT_MAX_C", "60"))
TELEGRAM_ALERT_SOIL_MARGIN = float(os.getenv("TELEGRAM_ALERT_SOIL_MARGIN", "0"))
TELEGRAM_SOIL_FAULT_ADC_MAX = int(os.getenv("TELEGRAM_SOIL_FAULT_ADC_MAX", "5"))
TELEGRAM_COMMANDS_ENABLED = env_bool("TELEGRAM_COMMANDS", default=True)
TELEGRAM_MANUAL_HOLD_SECONDS = max(0, int(os.getenv("TELEGRAM_MANUAL_HOLD_SECONDS", "900")))
TELEGRAM_FLAME_ACTIVE_VALUE = int(os.getenv("TELEGRAM_FLAME_ACTIVE_VALUE", "0"))
TELEGRAM_IR_ACTIVE_VALUE = int(os.getenv("TELEGRAM_IR_ACTIVE_VALUE", "0"))
TELEGRAM_STARTUP_BRIEFING = env_bool("TELEGRAM_STARTUP_BRIEFING", default=True)
FARMEASE_MODE = os.getenv("FARMEASE_MODE", "advisory").strip().lower() or "advisory"

TRAINING_COLUMNS = [
    "timestamp",
    "temp_c",
    "humidity_pct",
    "soil_adc",
    "light_lux",
    "flame_detected",
    "ir_detected",
    "relay_fan",
    "relay_pump",
    "relay_light",
    "relay_buzzer",
    "automation_on",
    "threshold_temp_on",
    "threshold_soil_dry",
    "threshold_light_lux"
]

training_state = {
    "temp_c": None,
    "humidity_pct": None,
    "soil_adc": None,
    "light_lux": None,
    "flame_detected": None,
    "ir_detected": None,
    "relay_fan": None,
    "relay_pump": None,
    "relay_light": None,
    "relay_buzzer": None,
    "automation_on": None
}

event_history = deque(maxlen=120)
EVENT_LOG_FILE = os.path.join(DATA_DIR, "event_timeline.csv")
TRAINING_REPORT_FILE = os.path.join("models", "training_report.json")

last_log_time = 0.0
logged_rows = 0

telegram_notifier = TelegramNotifier(
    bot_token=TELEGRAM_BOT_TOKEN,
    chat_id=TELEGRAM_CHAT_ID,
    enabled=TELEGRAM_ALERTS_ENABLED,
    default_cooldown_seconds=TELEGRAM_ALERT_COOLDOWN,
)

telegram_manual_override_lock = threading.Lock()
telegram_manual_override_active = False
telegram_manual_override_until = None

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)
    print(f"✓ Connected to {PORT} at {BAUD} baud")
except serial.SerialException as e:
    print(f"❌ Error opening serial port {PORT}: {e}")
    print("\nTroubleshooting:")
    print("1. Check if device is connected")
    print("2. Close Arduino IDE / Serial Monitor if open")
    print("3. Check Device Manager for correct COM port")
    print("4. Try unplugging and reconnecting the device")
    exit()
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    exit()

def ensure_training_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    file_exists = os.path.exists(TRAINING_DATA_FILE)
    with open(TRAINING_DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRAINING_COLUMNS)
        if not file_exists or os.path.getsize(TRAINING_DATA_FILE) == 0:
            writer.writeheader()


def ensure_event_log_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    file_exists = os.path.exists(EVENT_LOG_FILE)
    with open(EVENT_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["timestamp", "event_type", "severity", "source", "message"],
        )
        if not file_exists or os.path.getsize(EVENT_LOG_FILE) == 0:
            writer.writeheader()


def log_event(event_type, message, severity="info", source="system"):
    timestamp = datetime.now().isoformat(timespec="seconds")
    event = {
        "timestamp": timestamp,
        "event_type": str(event_type),
        "severity": str(severity),
        "source": str(source),
        "message": str(message),
    }
    event_history.append(event)
    try:
        with open(EVENT_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["timestamp", "event_type", "severity", "source", "message"],
            )
            writer.writerow(event)
    except Exception:
        pass

def get_logged_row_count():
    try:
        with open(TRAINING_DATA_FILE, "r", encoding="utf-8") as f:
            return max(sum(1 for _ in f) - 1, 0)
    except Exception:
        return 0

def parse_number(text):
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None

def parse_binary_state(text):
    value = text.strip().lower()
    truthy = {"1", "on", "high", "detected", "true", "yes"}
    falsy = {"0", "off", "low", "clear", "none", "false", "no"}
    if value in truthy:
        return 1
    if value in falsy:
        return 0
    return None

def update_training_state(key, value):
    if value is not None:
        training_state[key] = value

def get_slider_value(name, default):
    slider = globals().get(name)
    return int(slider.get()) if slider else default

def get_training_row():
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "temp_c": training_state["temp_c"],
        "humidity_pct": training_state["humidity_pct"],
        "soil_adc": training_state["soil_adc"],
        "light_lux": training_state["light_lux"],
        "flame_detected": training_state["flame_detected"],
        "ir_detected": training_state["ir_detected"],
        "relay_fan": training_state["relay_fan"],
        "relay_pump": training_state["relay_pump"],
        "relay_light": training_state["relay_light"],
        "relay_buzzer": training_state["relay_buzzer"],
        "automation_on": training_state["automation_on"],
        "threshold_temp_on": get_slider_value("temp_slider", 28),
        "threshold_soil_dry": get_slider_value("soil_slider", 1800),
        "threshold_light_lux": get_slider_value("light_slider", 5)
    }
    return row

def update_logger_counter():
    if "logger_badge" in globals():
        logger_badge.config(text=f"Rows saved: {logged_rows}")

    if "progress_var" in globals() and "progress_label" in globals():
        percent = min((logged_rows / MODEL_READY_ROWS) * 100.0, 100.0) if MODEL_READY_ROWS > 0 else 0
        progress_var.set(percent)
        progress_label.config(text=f"Training data progress: {logged_rows}/{MODEL_READY_ROWS} rows ({percent:.1f}%)")

def maybe_log_training_row(force=False):
    global last_log_time, logged_rows
    now = time.time()
    if not force and (now - last_log_time) < LOG_INTERVAL_SECONDS:
        return

    row = get_training_row()
    with open(TRAINING_DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRAINING_COLUMNS)
        writer.writerow(row)

    last_log_time = now
    logged_rows += 1
    update_logger_counter()


def maybe_send_telegram_alerts():
    if not telegram_notifier.is_configured():
        return

    temp_value = training_state.get("temp_c")
    temp_threshold = get_slider_value("temp_slider", 28) + TELEGRAM_ALERT_TEMP_OFFSET
    if is_temp_sensor_fault(temp_value):
        sent = telegram_notifier.send_with_cooldown(
            key="temp_sensor_fault",
            text=(
                "⚠ Sensor Warning\n"
                f"Temperature sensor appears faulty (Temp={temp_value:.2f} °C). "
                "High-temperature alert logic is temporarily ignored."
            ),
            cooldown_seconds=600,
        )
        if sent:
            log_event("sensor", f"Temperature sensor fault detected ({temp_value:.2f} °C)", severity="warning", source="sensor")
    elif temp_value is not None and temp_value >= temp_threshold:
        sent = telegram_notifier.send_with_cooldown(
            key="high_temp",
            text=(
                f"🌡 Greenhouse Alert\n"
                f"High temperature detected: {temp_value:.2f} °C\n"
                f"Threshold: {temp_threshold:.2f} °C"
            ),
        )
        if sent:
            log_event("alert", f"High temperature alert at {temp_value:.2f} °C", severity="warning", source="automation")

    soil_value = training_state.get("soil_adc")
    soil_threshold = get_slider_value("soil_slider", 1800) - TELEGRAM_ALERT_SOIL_MARGIN
    if is_soil_sensor_fault(soil_value):
        sent = telegram_notifier.send_with_cooldown(
            key="soil_sensor_fault",
            text=(
                "⚠ Sensor Warning\n"
                f"Soil sensor appears faulty (ADC={soil_value:.0f}). "
                "Dry-soil alert logic is temporarily ignored."
            ),
            cooldown_seconds=600,
        )
        if sent:
            log_event("sensor", f"Soil sensor fault detected ({soil_value:.0f} ADC)", severity="warning", source="sensor")
    elif soil_value is not None and soil_value <= soil_threshold:
        sent = telegram_notifier.send_with_cooldown(
            key="dry_soil",
            text=(
                f"🌱 Greenhouse Alert\n"
                f"Soil dry condition detected: {soil_value:.0f} ADC\n"
                f"Threshold: {soil_threshold:.0f} ADC"
            ),
        )
        if sent:
            log_event("alert", f"Dry soil alert at {soil_value:.0f} ADC", severity="warning", source="automation")

    flame_value = training_state.get("flame_detected")
    if flame_value is not None and int(flame_value) == TELEGRAM_FLAME_ACTIVE_VALUE:
        sent = telegram_notifier.send_with_cooldown(
            key="flame_detected",
            text="🔥 Safety Alert\nFlame sensor detected fire risk. Please check greenhouse immediately.",
            cooldown_seconds=60,
        )
        if sent:
            log_event("alert", "Flame sensor safety alert", severity="critical", source="automation")

    motion_value = training_state.get("ir_detected")
    if motion_value is not None and int(motion_value) == TELEGRAM_IR_ACTIVE_VALUE:
        sent = telegram_notifier.send_with_cooldown(
            key="ir_motion",
            text="👀 Security Alert\nIR motion detected in greenhouse area.",
            cooldown_seconds=120,
        )
        if sent:
            log_event("alert", "IR motion alert", severity="warning", source="automation")

    risk = compute_risk_snapshot()
    if risk["score"] >= 80:
        sent = telegram_notifier.send_with_cooldown(
            key="critical_risk",
            text=(
                "🚨 Critical Greenhouse Risk\n"
                f"Risk Score: {risk['score']}/100 ({risk['level']})\n"
                f"Reason: {', '.join(risk['reasons'][:3])}"
            ),
            cooldown_seconds=90,
        )
        if sent:
            log_event("alert", f"Critical risk alert ({risk['score']}/100)", severity="critical", source="automation")


def format_binary_state(value):
    if value is None:
        return "--"
    return "ON" if int(value) == 1 else "OFF"


def is_soil_sensor_fault(soil_value):
    if soil_value is None:
        return False
    try:
        return float(soil_value) <= float(TELEGRAM_SOIL_FAULT_ADC_MAX)
    except Exception:
        return False


def is_temp_sensor_fault(temp_value):
    if temp_value is None:
        return False
    try:
        value = float(temp_value)
        return value <= float(TELEGRAM_TEMP_FAULT_MIN_C) or value >= float(TELEGRAM_TEMP_FAULT_MAX_C)
    except Exception:
        return True


def compute_risk_snapshot():
    score = 0
    reasons = []

    temp_value = training_state.get("temp_c")
    temp_fault = is_temp_sensor_fault(temp_value)
    soil_value = training_state.get("soil_adc")
    soil_fault = is_soil_sensor_fault(soil_value)
    flame_value = training_state.get("flame_detected")
    ir_value = training_state.get("ir_detected")

    temp_threshold = get_slider_value("temp_slider", 28)
    soil_threshold = get_slider_value("soil_slider", 1800)

    if flame_value is not None and int(flame_value) == TELEGRAM_FLAME_ACTIVE_VALUE:
        score += 70
        reasons.append("flame sensor triggered")

    if ir_value is not None and int(ir_value) == TELEGRAM_IR_ACTIVE_VALUE:
        score += 25
        reasons.append("IR motion detected")

    if temp_fault:
        reasons.append(f"temperature sensor fault ({temp_value:.2f}°C)")
    elif temp_value is not None and temp_value >= temp_threshold:
        temp_over = max(0.0, float(temp_value) - float(temp_threshold))
        score += min(20, int(5 + (temp_over * 3)))
        reasons.append(f"temperature above threshold ({temp_value:.1f}°C)")

    if soil_fault:
        reasons.append(f"soil sensor fault ({soil_value:.0f} ADC)")
    elif soil_value is not None and soil_value <= soil_threshold:
        dryness = max(0.0, float(soil_threshold) - float(soil_value))
        score += min(15, int(4 + (dryness / 120)))
        reasons.append(f"soil is dry ({soil_value:.0f} ADC)")

    score = min(int(score), 100)

    if score >= 80:
        level = "CRITICAL"
    elif score >= 50:
        level = "HIGH"
    elif score >= 25:
        level = "MEDIUM"
    else:
        level = "LOW"

    advice = []
    if any("flame" in item for item in reasons):
        advice.append("Inspect greenhouse immediately and cut high-power loads if safe")
    if any("IR motion" in item for item in reasons):
        advice.append("Check for intrusion/animal movement and verify perimeter")
    if any("temperature" in item for item in reasons):
        advice.append("Increase cooling/ventilation and monitor humidity drift")
    if any("temperature sensor fault" in item for item in reasons):
        advice = [item for item in advice if "cooling" not in item.lower() and "ventilation" not in item.lower()]
        advice.append("Check DHT22 wiring/power; high-temperature automation is currently ignored")
    if any("soil" in item for item in reasons):
        advice.append("Start short irrigation cycle and re-check soil after 2-3 minutes")
    if any("soil sensor fault" in item for item in reasons):
        advice = [item for item in advice if "irrigation" not in item.lower()]
        advice.append("Check soil sensor wiring/probe; dry-soil automation is currently ignored")
    if not advice:
        advice.append("System stable. Keep monitoring.")

    return {
        "score": score,
        "level": level,
        "reasons": reasons or ["no active risk factors"],
        "advice": advice,
    }


def build_telegram_status_text():
    automation_value = training_state.get("automation_on")
    automation_text = "UNKNOWN"
    if automation_value is not None:
        automation_text = "ON" if int(automation_value) == 1 else "OFF"

    temp_value = training_state.get("temp_c")
    if temp_value is None:
        temp_text = "--"
    elif is_temp_sensor_fault(temp_value):
        temp_text = f"SENSOR FAULT ({temp_value:.2f} °C)"
    else:
        temp_text = f"{temp_value:.2f} °C"
    humidity_text = "--" if training_state.get("humidity_pct") is None else f"{training_state['humidity_pct']:.2f} %"
    soil_value = training_state.get("soil_adc")
    if soil_value is None:
        soil_text = "--"
    elif is_soil_sensor_fault(soil_value):
        soil_text = f"SENSOR FAULT ({soil_value:.0f} ADC)"
    else:
        soil_text = f"{soil_value:.0f} ADC"
    light_text = "--" if training_state.get("light_lux") is None else f"{training_state['light_lux']:.2f} lux"
    risk = compute_risk_snapshot()

    return (
        "📊 Greenhouse Status\n"
        f"Mode: {FARMEASE_MODE}\n"
        f"Risk Score: {risk['score']}/100 ({risk['level']})\n"
        f"Automation: {automation_text}\n"
        f"Fan: {format_binary_state(training_state.get('relay_fan'))}\n"
        f"Pump: {format_binary_state(training_state.get('relay_pump'))}\n"
        f"Light: {format_binary_state(training_state.get('relay_light'))}\n"
        f"Buzzer: {format_binary_state(training_state.get('relay_buzzer'))}\n"
        f"Temp: {temp_text}\n"
        f"Humidity: {humidity_text}\n"
        f"Soil: {soil_text}\n"
        f"Light Sensor: {light_text}"
    )


def build_telegram_advice_text():
    risk = compute_risk_snapshot()
    advice_lines = "\n".join([f"- {item}" for item in risk["advice"]])
    reasons_lines = "\n".join([f"- {item}" for item in risk["reasons"][:4]])
    return (
        "🧠 Greenhouse AI Advice\n"
        f"Risk Score: {risk['score']}/100 ({risk['level']})\n"
        "Top Signals:\n"
        f"{reasons_lines}\n"
        "Recommended Actions:\n"
        f"{advice_lines}"
    )


def build_telegram_history_text(limit=8):
    if not event_history:
        return "🗂 Event History\nNo events captured yet in this run."

    recent = list(event_history)[-max(1, int(limit)):]
    lines = []
    for event in recent:
        lines.append(
            f"{event['timestamp'][11:19]} [{event['severity'].upper()}] {event['source']}: {event['message']}"
        )
    return "🗂 Event History (latest)\n" + "\n".join(lines)


def build_dashboard_advice_text():
    risk = compute_risk_snapshot()
    top_advice = risk["advice"][0] if risk["advice"] else "System stable. Keep monitoring."
    return f"AI Advice ({risk['level']}): {top_advice}"


def update_dashboard_advice():
    if "advice_banner" in globals():
        advice_banner.config(text=build_dashboard_advice_text())


def get_model_status_text():
    if not os.path.exists(TRAINING_REPORT_FILE):
        return "Model: no training report found"

    try:
        import json
        with open(TRAINING_REPORT_FILE, "r", encoding="utf-8") as f:
            report = json.load(f)

        best = report.get("best_models", {})
        relay_model = best.get("relay_light") or "not-produced"
        light_model = best.get("light_forecast") or "unknown"

        gate = report.get("quality_gate", {}).get("relay_light", {})
        gate_status = "pass" if gate.get("passed", False) else "warn"

        return f"Model: light={light_model}, relay={relay_model}, gate={gate_status}"
    except Exception:
        return "Model: report unreadable"


def send_startup_briefing():
    if not telegram_notifier.is_configured() or not TELEGRAM_STARTUP_BRIEFING:
        return

    risk = compute_risk_snapshot()
    briefing = (
        "🚀 FarmEase System Online\n"
        f"Mode: {FARMEASE_MODE}\n"
        f"Connection: {PORT} @ {BAUD}\n"
        f"Risk: {risk['score']}/100 ({risk['level']})\n"
        f"{get_model_status_text()}\n"
        "Use /menu for controls"
    )

    ok, _ = telegram_notifier.send_message(briefing)
    if ok:
        log_event("startup", "Startup briefing sent to Telegram", severity="info", source="system")


def build_telegram_help_text():
    return (
        "🤖 FarmEase Commands\n"
        "/status\n"
        "/risk\n"
        "/advice\n"
        "/history\n"
        "/fan_on /fan_off\n"
        "/pump_on /pump_off\n"
        "/light_on /light_off\n"
        "/buzzer_on /buzzer_off\n"
        "/automation_on /automation_off\n"
        "/all_off\n"
        "/menu"
    )


def build_telegram_keyboard():
    return {
        "keyboard": [
            [{"text": "/status"}, {"text": "/risk"}],
            [{"text": "/advice"}, {"text": "/history"}],
            [{"text": "/all_off"}],
            [{"text": "/fan_on"}, {"text": "/fan_off"}],
            [{"text": "/pump_on"}, {"text": "/pump_off"}],
            [{"text": "/light_on"}, {"text": "/light_off"}],
            [{"text": "/buzzer_on"}, {"text": "/buzzer_off"}],
            [{"text": "/automation_on"}, {"text": "/automation_off"}],
            [{"text": "/help"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }

ensure_training_file()
ensure_event_log_file()
logged_rows = get_logged_row_count()

# ---------- ROOT WINDOW ----------
root = tk.Tk()
root.title("🌿 Smart Greenhouse Dashboard")
root.geometry("1180x760")
root.minsize(1040, 680)

COLORS = {
    "bg": "#edf2f7",
    "panel": "#ffffff",
    "panel_soft": "#f8fafc",
    "accent": "#2e7d32",
    "accent_alt": "#1565c0",
    "warning": "#ef6c00",
    "danger": "#c62828",
    "text": "#1f2937",
    "muted": "#64748b"
}

root.configure(bg=COLORS["bg"])

style = ttk.Style(root)
style.theme_use("clam")
style.configure(
    "Training.Horizontal.TProgressbar",
    troughcolor="#dbe5ef",
    background=COLORS["accent_alt"],
    bordercolor="#dbe5ef",
    lightcolor=COLORS["accent_alt"],
    darkcolor=COLORS["accent_alt"]
)

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SUBTITLE = ("Segoe UI", 10)
FONT_LABEL = ("Segoe UI", 11, "bold")
FONT_VALUE = ("Segoe UI", 12)
FONT_VALUE_BOLD = ("Segoe UI", 12, "bold")
FONT_BUTTON = ("Segoe UI", 10, "bold")

def make_card(parent, title):
    frame = tk.LabelFrame(
        parent,
        text=title,
        font=FONT_LABEL,
        bg=COLORS["panel"],
        fg=COLORS["text"],
        padx=14,
        pady=12,
        bd=1,
        relief="groove"
    )
    return frame

root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)

# ---------- HEADER ----------
header = tk.Frame(root, bg=COLORS["bg"])
header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
header.grid_columnconfigure(0, weight=1)

title_block = tk.Frame(header, bg=COLORS["bg"])
title_block.grid(row=0, column=0, sticky="w")

tk.Label(
    title_block,
    text="🌿 Smart Greenhouse Dashboard",
    font=FONT_TITLE,
    bg=COLORS["bg"],
    fg=COLORS["text"]
).grid(row=0, column=0, sticky="w")

tk.Label(
    title_block,
    text="Live monitoring and manual automation controls",
    font=FONT_SUBTITLE,
    bg=COLORS["bg"],
    fg=COLORS["muted"]
).grid(row=1, column=0, sticky="w", pady=(2, 0))

connection_badge = tk.Label(
    header,
    text=f"Connected: {PORT} @ {BAUD}",
    font=("Segoe UI", 10, "bold"),
    bg="#e8f5e9",
    fg=COLORS["accent"],
    padx=12,
    pady=7
)
connection_badge.grid(row=0, column=1, rowspan=2, sticky="e")

logger_badge = tk.Label(
    header,
    text=f"Rows saved: {logged_rows}",
    font=("Segoe UI", 10, "bold"),
    bg="#ede7f6",
    fg="#5e35b1",
    padx=12,
    pady=7
)
logger_badge.grid(row=2, column=1, sticky="e", pady=(6, 0))

telegram_status_label = tk.Label(
    header,
    text="Telegram: ON" if telegram_notifier.is_configured() else "Telegram: OFF",
    font=("Segoe UI", 10, "bold"),
    bg="#e8f5e9" if telegram_notifier.is_configured() else "#ffebee",
    fg=COLORS["accent"] if telegram_notifier.is_configured() else COLORS["danger"],
    padx=12,
    pady=7
)
telegram_status_label.grid(row=3, column=1, sticky="e", pady=(6, 0))

progress_wrap = tk.Frame(header, bg=COLORS["bg"])
progress_wrap.grid(row=2, column=0, sticky="ew", pady=(6, 0), padx=(0, 12))
progress_wrap.grid_columnconfigure(0, weight=1)

progress_label = tk.Label(
    progress_wrap,
    text="Training data progress: 0/1000 rows (0.0%)",
    font=("Segoe UI", 9, "bold"),
    bg=COLORS["bg"],
    fg=COLORS["muted"],
    anchor="w"
)
progress_label.grid(row=0, column=0, sticky="w")

progress_var = tk.DoubleVar(value=0.0)
progress_bar = ttk.Progressbar(
    progress_wrap,
    orient="horizontal",
    mode="determinate",
    maximum=100,
    variable=progress_var,
    style="Training.Horizontal.TProgressbar"
)
progress_bar.grid(row=1, column=0, sticky="ew", pady=(4, 0), ipady=4)

advice_banner = tk.Label(
    header,
    text="AI Advice: waiting for live data...",
    font=("Segoe UI", 9, "bold"),
    bg="#fff3cd",
    fg="#7c4d00",
    padx=12,
    pady=7,
    anchor="w",
)
advice_banner.grid(row=3, column=0, sticky="ew", pady=(6, 0), padx=(0, 12))

update_logger_counter()
update_dashboard_advice()

# ---------- MAIN LAYOUT ----------
content = tk.Frame(root, bg=COLORS["bg"])
content.grid(row=1, column=0, sticky="nsew", padx=18, pady=8)
content.grid_columnconfigure(0, weight=3)
content.grid_columnconfigure(1, weight=4)
content.grid_rowconfigure(0, weight=3)
content.grid_rowconfigure(1, weight=2)

left_col = tk.Frame(content, bg=COLORS["bg"])
left_col.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
left_col.grid_rowconfigure(0, weight=3)
left_col.grid_rowconfigure(1, weight=2)
left_col.grid_columnconfigure(0, weight=1)

right_col = tk.Frame(content, bg=COLORS["bg"])
right_col.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(10, 0))
right_col.grid_rowconfigure(0, weight=1)
right_col.grid_rowconfigure(1, weight=2)
right_col.grid_rowconfigure(2, weight=2)
right_col.grid_columnconfigure(0, weight=1)

# ---------- SENSOR FRAME ----------
sensor_frame = make_card(left_col, "Sensor Readings")
sensor_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
sensor_frame.grid_columnconfigure(1, weight=1)

data_labels = {}
sensor_vars = {}
sensors = ["Temp","Humidity","Soil","Lux","Flame","IR"]
sense_emoji = {
    "Temp": "🌡",
    "Humidity": "💧",
    "Soil": "🌱",
    "Lux": "💡",
    "Flame": "🔥",
    "IR": "👀"
}

for i, sensor in enumerate(sensors):
    tk.Label(
        sensor_frame,
        text=f"{sense_emoji[sensor]} {sensor}",
        font=FONT_LABEL,
        bg=COLORS["panel"],
        fg=COLORS["text"]
    ).grid(row=i, column=0, sticky="w", padx=4, pady=7)

    lbl = tk.Label(
        sensor_frame,
        text="--",
        font=FONT_VALUE_BOLD,
        bg=COLORS["panel"],
        fg=COLORS["accent_alt"],
        anchor="w"
    )
    lbl.grid(row=i, column=1, sticky="w")
    data_labels[sensor] = lbl

    var = tk.BooleanVar(value=True)
    chk = tk.Checkbutton(
        sensor_frame,
        text="Enabled",
        variable=var,
        font=("Segoe UI", 9, "bold"),
        bg=COLORS["panel"],
        fg=COLORS["muted"],
        activebackground=COLORS["panel"],
        selectcolor="#e6f4ea",
        highlightthickness=0,
        bd=0,
        cursor="hand2"
    )
    chk.grid(row=i, column=2, padx=(8, 0), sticky="e")
    sensor_vars[sensor] = var

    # Send toggle to ESP32
    def callback(s=sensor, v=var):
        val = 1 if v.get() else 0
        send_cmd(f"X{s[0]}{val}\n")
    var.trace_add('write', lambda *args, s=sensor, v=var: callback(s, v))

# ---------- RELAY FRAME ----------
relay_frame = make_card(left_col, "Relay States")
relay_frame.grid(row=1, column=0, sticky="nsew")
relay_frame.grid_columnconfigure(1, weight=1)

relay_labels = {}
relays = ["Fan", "Pump", "Light", "Buzzer"]
for i, relay in enumerate(relays):
    tk.Label(
        relay_frame,
        text=relay,
        font=FONT_LABEL,
        bg=COLORS["panel"],
        fg=COLORS["text"]
    ).grid(row=i, column=0, sticky="w", padx=4, pady=8)

    lbl = tk.Label(
        relay_frame,
        text="OFF",
        font=FONT_VALUE_BOLD,
        fg=COLORS["danger"],
        bg=COLORS["panel_soft"],
        padx=10,
        pady=3
    )
    lbl.grid(row=i, column=1, sticky="w")
    relay_labels[relay] = lbl

# ---------- AUTOMATION ----------
automation_on = True
automation_frame = make_card(right_col, "Automation")
automation_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
automation_frame.grid_columnconfigure(0, weight=1)
automation_frame.grid_columnconfigure(1, weight=1)

automation_label = tk.Label(
    automation_frame,
    text="Automation: ON",
    font=FONT_VALUE_BOLD,
    fg=COLORS["accent"],
    bg=COLORS["panel"]
)
automation_label.grid(row=0, column=0, sticky="w")

def toggle_automation():
    global automation_on
    send_cmd('A' if not automation_on else 'a')

tk.Button(
    automation_frame,
    text="Toggle Automation",
    command=toggle_automation,
    width=18,
    font=FONT_BUTTON,
    bg=COLORS["warning"],
    fg="white",
    activebackground="#f57c00",
    activeforeground="white",
    relief="flat",
    cursor="hand2"
).grid(row=0, column=1, sticky="e")

# ---------- RELAY BUTTONS ----------
btn_frame = make_card(right_col, "Manual Relay Control")
btn_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
btn_frame.grid_columnconfigure(0, weight=1)
btn_frame.grid_columnconfigure(1, weight=1)

def send_cmd(cmd):
    try:
        ser.write(cmd.encode())
        ser.flush()
        command_labels = {
            "F": "Fan ON",
            "f": "Fan OFF",
            "P": "Pump ON",
            "p": "Pump OFF",
            "L": "Light ON",
            "l": "Light OFF",
            "B": "Buzzer ON",
            "b": "Buzzer OFF",
            "A": "Automation ON",
            "a": "Automation OFF",
        }
        if cmd in command_labels:
            log_event("control", command_labels[cmd], severity="info", source="command")
    except Exception:
        pass


def clear_telegram_manual_override():
    global telegram_manual_override_active, telegram_manual_override_until
    with telegram_manual_override_lock:
        telegram_manual_override_active = False
        telegram_manual_override_until = None


def start_telegram_manual_override():
    global telegram_manual_override_active, telegram_manual_override_until
    send_cmd("a")
    with telegram_manual_override_lock:
        telegram_manual_override_active = True
        if TELEGRAM_MANUAL_HOLD_SECONDS > 0:
            telegram_manual_override_until = time.time() + TELEGRAM_MANUAL_HOLD_SECONDS
        else:
            telegram_manual_override_until = None


def get_telegram_manual_override_remaining_seconds():
    with telegram_manual_override_lock:
        if not telegram_manual_override_active:
            return 0
        if telegram_manual_override_until is None:
            return None
        return max(0, int(telegram_manual_override_until - time.time()))


def maybe_resume_automation_after_manual_override():
    should_resume = False
    with telegram_manual_override_lock:
        if telegram_manual_override_active and telegram_manual_override_until is not None:
            if time.time() >= telegram_manual_override_until:
                should_resume = True
    if should_resume:
        send_cmd("A")
        clear_telegram_manual_override()
        log_event("control", "Telegram manual hold expired; automation resumed", severity="info", source="telegram")


def parse_telegram_command(text):
    raw = (text or "").strip()
    if not raw:
        return "", None

    first_token = raw.split()[0].lower()
    if first_token.startswith("/") and "@" in first_token:
        first_token = first_token.split("@", 1)[0]

    relay_command_map = {
        "/fan_on": ("F", "✅ Fan ON command sent"),
        "/fan_off": ("f", "✅ Fan OFF command sent"),
        "/pump_on": ("P", "✅ Pump ON command sent"),
        "/pump_off": ("p", "✅ Pump OFF command sent"),
        "/light_on": ("L", "✅ Light ON command sent"),
        "/light_off": ("l", "✅ Light OFF command sent"),
        "/buzzer_on": ("B", "✅ Buzzer ON command sent"),
        "/buzzer_off": ("b", "✅ Buzzer OFF command sent"),
    }

    automation_command_map = {
        "/automation_on": ("A", "✅ Automation ON command sent"),
        "/automation_off": ("a", "✅ Automation OFF command sent"),
    }

    if first_token in {"/start", "/help", "/menu"}:
        return build_telegram_help_text(), build_telegram_keyboard()

    if first_token == "/status":
        return build_telegram_status_text(), None

    if first_token == "/risk":
        risk = compute_risk_snapshot()
        return f"📈 Risk Score: {risk['score']}/100 ({risk['level']})", None

    if first_token == "/advice":
        return build_telegram_advice_text(), None

    if first_token == "/history":
        return build_telegram_history_text(limit=8), None

    if first_token == "/all_off":
        start_telegram_manual_override()
        for relay_cmd in ("f", "p", "l", "b"):
            send_cmd(relay_cmd)
        remaining = get_telegram_manual_override_remaining_seconds()
        if remaining is None:
            return "✅ All relays OFF command sent (manual override active until /automation_on)", None
        return f"✅ All relays OFF command sent (manual override for {remaining}s)", None

    relay_command_pair = relay_command_map.get(first_token)
    if relay_command_pair:
        start_telegram_manual_override()
        serial_cmd, reply_text = relay_command_pair
        send_cmd(serial_cmd)
        remaining = get_telegram_manual_override_remaining_seconds()
        if remaining is None:
            return f"{reply_text} (manual override active until /automation_on)", None
        return f"{reply_text} (manual override for {remaining}s)", None

    automation_command_pair = automation_command_map.get(first_token)
    if automation_command_pair:
        serial_cmd, reply_text = automation_command_pair
        send_cmd(serial_cmd)
        clear_telegram_manual_override()
        return reply_text, None

    return "Unknown command. Use /help", None

btns = [
    ("Fan ON","F"),("Fan OFF","f"),
    ("Pump ON","P"),("Pump OFF","p"),
    ("Light ON","L"),("Light OFF","l"),
    ("Buzzer ON","B"),("Buzzer OFF","b"),
]

for i, (text, cmd) in enumerate(btns):
    is_on = "ON" in text
    tk.Button(
        btn_frame,
        text=text,
        command=lambda c=cmd: send_cmd(c),
        width=16,
        font=FONT_BUTTON,
        bg=COLORS["accent"] if is_on else "#455a64",
        fg="white",
        activebackground="#1b5e20" if is_on else "#263238",
        activeforeground="white",
        relief="flat",
        cursor="hand2",
        pady=4
    ).grid(row=i // 2, column=i % 2, padx=6, pady=6, sticky="ew")

# ---------- SENSORS SLIDERS ----------
slider_frame = make_card(right_col, "Sensor Sensitivity")
slider_frame.grid(row=2, column=0, sticky="nsew")
slider_frame.grid_columnconfigure(1, weight=1)

def send_slider_value(param, val):
    send_cmd(f"S{param}{int(float(val))}\n")

tk.Label(
    slider_frame,
    text="Temp ON (°C)",
    bg=COLORS["panel"],
    fg=COLORS["text"],
    font=FONT_VALUE
).grid(row=0, column=0, sticky="w", pady=(2, 8))

temp_slider = tk.Scale(slider_frame, from_=20, to=40, orient=tk.HORIZONTAL,
                       command=lambda val: send_slider_value('T', val),
                       bg=COLORS["panel"],
                       troughcolor="#dbeafe",
                       highlightthickness=0,
                       activebackground=COLORS["accent_alt"])
temp_slider.set(28)
temp_slider.grid(row=0, column=1, sticky="we", pady=(2, 8))

tk.Label(
    slider_frame,
    text="Soil Dry (ADC)",
    bg=COLORS["panel"],
    fg=COLORS["text"],
    font=FONT_VALUE
).grid(row=1, column=0, sticky="w", pady=8)

soil_slider = tk.Scale(slider_frame, from_=1000, to=3000, orient=tk.HORIZONTAL,
                       command=lambda val: send_slider_value('S', val),
                       bg=COLORS["panel"],
                       troughcolor="#dcfce7",
                       highlightthickness=0,
                       activebackground=COLORS["accent"])
soil_slider.set(1800)
soil_slider.grid(row=1, column=1, sticky="we", pady=8)

tk.Label(
    slider_frame,
    text="Light Threshold (lux)",
    bg=COLORS["panel"],
    fg=COLORS["text"],
    font=FONT_VALUE
).grid(row=2, column=0, sticky="w", pady=(8, 2))

light_slider = tk.Scale(slider_frame, from_=1, to=50, orient=tk.HORIZONTAL,
                        command=lambda val: send_slider_value('L', val),
                        bg=COLORS["panel"],
                        troughcolor="#fff3cd",
                        highlightthickness=0,
                        activebackground=COLORS["warning"])
light_slider.set(5)
light_slider.grid(row=2, column=1, sticky="we", pady=(8, 2))

# ---------- STATUS BAR ----------
status_bar = tk.Label(
    root,
    text=f"Ready • Logging to {TRAINING_DATA_FILE}",
    anchor="w",
    bg="#dde6ee",
    fg=COLORS["muted"],
    font=("Segoe UI", 9),
    padx=12,
    pady=6
)
status_bar.grid(row=2, column=0, sticky="ew")

# ---------- SERIAL READER ----------
def process_serial_line(line):
    global automation_on
    if not line:
        return

    status_bar.config(text=f"Live data • {line[:90]}")

    if "🌡 Temp" in line:
        temp_text = line.split("🌡 Temp:")[1].strip()
        update_training_state("temp_c", parse_number(temp_text))
        if sensor_vars["Temp"].get():
            data_labels["Temp"].config(text=temp_text)

    if "💧 Hum" in line:
        humidity_text = line.split("💧 Hum:")[1].strip()
        update_training_state("humidity_pct", parse_number(humidity_text))
        if sensor_vars["Humidity"].get():
            data_labels["Humidity"].config(text=humidity_text)

    if "🌱 Soil ADC:" in line:
        soil_text = line.split(":")[1].strip()
        update_training_state("soil_adc", parse_number(soil_text))
        if sensor_vars["Soil"].get():
            data_labels["Soil"].config(text=soil_text)

    if "💡 Light:" in line:
        light_text = line.split(":")[1].strip()
        update_training_state("light_lux", parse_number(light_text))
        if sensor_vars["Lux"].get():
            data_labels["Lux"].config(text=light_text)

    if "🔥 Flame:" in line and "👀 IR:" in line:
        parts = line.replace("🔥 Flame:","").replace("👀 IR:","").split()
        if len(parts) >= 2:
            update_training_state("flame_detected", parse_binary_state(parts[0]))
            update_training_state("ir_detected", parse_binary_state(parts[1]))
            if sensor_vars["Flame"].get():
                data_labels["Flame"].config(text=parts[0])
            if sensor_vars["IR"].get():
                data_labels["IR"].config(text=parts[1])

    if "RelayStates:" in line:
        states = line.replace("RelayStates:","").split()
        for i, relay in enumerate(relays):
            if i < len(states):
                state = "ON" if states[i]=="1" else "OFF"
                key = f"relay_{relay.lower()}"
                update_training_state(key, 1 if state == "ON" else 0)
                relay_labels[relay].config(
                    text=state,
                    fg=COLORS["accent"] if state=="ON" else COLORS["danger"],
                    bg="#e8f5e9" if state=="ON" else "#ffebee"
                )

    if "Automation:" in line:
        status = line.split("Automation:")[1].strip()
        automation_on = (status == "ON")
        update_training_state("automation_on", 1 if automation_on else 0)
        automation_label.config(
            text=f"Automation: {status}",
            fg=COLORS["accent"] if automation_on else COLORS["danger"]
        )

    maybe_log_training_row()
    maybe_send_telegram_alerts()
    update_dashboard_advice()


def read_serial():
    while True:
        try:
            line = ser.readline().decode(errors="ignore").strip()
            process_serial_line(line)

        except Exception as e:
            print("Serial read error:", e)
            status_bar.config(text="Serial read warning • Check USB connection")


def process_telegram_updates(next_offset):
    maybe_resume_automation_after_manual_override()
    ok, updates, _ = telegram_notifier.get_updates(offset=next_offset, timeout_seconds=20)
    if not ok:
        return next_offset, False

    for update in updates:
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            candidate_offset = update_id + 1
            next_offset = candidate_offset if next_offset is None else max(next_offset, candidate_offset)

        message = update.get("message") or update.get("edited_message")
        if not isinstance(message, dict):
            continue

        chat = message.get("chat") or {}
        message_chat_id = str(chat.get("id", "")).strip()
        if message_chat_id != str(telegram_notifier.chat_id):
            continue

        message_text = message.get("text")
        if not isinstance(message_text, str):
            continue

        reply, reply_markup = parse_telegram_command(message_text)
        if reply:
            telegram_notifier.send_message_async(reply, reply_markup=reply_markup)

    return next_offset, True


def poll_telegram_commands():
    next_offset = None
    while True:
        try:
            next_offset, ok = process_telegram_updates(next_offset)
            if not ok:
                time.sleep(3)
        except Exception:
            time.sleep(3)

def on_close():
    try:
        maybe_log_training_row(force=True)
    except Exception:
        pass
    try:
        ser.close()
    except Exception:
        pass
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

threading.Thread(target=read_serial, daemon=True).start()
if telegram_notifier.is_configured() and TELEGRAM_COMMANDS_ENABLED:
    threading.Thread(target=poll_telegram_commands, daemon=True).start()
send_startup_briefing()
root.mainloop()
