# FarmEase 3-5 Minute Demo Script

## Demo objective
Show end-to-end smart greenhouse operation: sensor ingest -> decision/actuation -> alerts -> ML evidence.

## Connectivity statement (say this explicitly)
- "In this prototype, there is no onboard Wi-Fi module on the controller path, so direct cloud sync is intentionally not part of the core design."
- "We use local-first serial control and logging on the laptop dashboard, with Telegram as the remote alert/command channel."
- "If a Wi-Fi module is added, we will push telemetry to cloud via MQTT/HTTPS and keep local safety checks as the gate before executing any remote command."

## Demo setup (before judges arrive)
- Start dashboard:

```powershell
.\scripts\run_dashboard.ps1
```

- Confirm serial connection shows as connected in dashboard console.
- Keep these files ready to show:
  - `docs/EVENT_EVIDENCE.md`
  - `models/training_report.json`
  - `data/event_timeline.csv`

## Timed flow

### 0:00-0:40 | Problem and impact
- "FarmEase reduces manual greenhouse monitoring by automating irrigation/light decisions and safety alerts."
- Show the latest hard number from `docs/EVENT_EVIDENCE.md`:
  - `Estimated irrigation runtime avoided vs always-on baseline`.

### 0:40-1:45 | Live telemetry and local control
- Point to live sensor cards (temperature, humidity, soil, light).
- Trigger one safe control action from dashboard (example: light ON then OFF).
- Expected outcome:
  - Relay state changes in UI.
  - Command event appears in `data/event_timeline.csv`.

### 1:45-2:40 | Safety and reliability behavior
- Trigger a detectable alert condition (flame/IR simulation if hardware supports).
- Expected outcome:
  - Critical/warning alert appears in dashboard.
  - Event logged with timestamp and severity in `data/event_timeline.csv`.
- Explain sensor-fault handling:
  - If sensor values are implausible, system logs a sensor warning.

### 2:40-3:40 | ML evidence
- Open `models/training_report.json`.
- Call out metrics:
  - Light forecast: MAE / RMSE
  - Relay classifier: F1 / ROC-AUC
- Mention quality gate status for relay model (`passed: true/false`).

### 3:40-4:30 | Fallback and resilience
- "Control logic is local-first: if internet/Telegram fails, dashboard and serial control continue."
- Show fallback notes from `docs/EVENT_FALLBACK_PLAN.md`.

### 4:30-4:45 | Future Wi-Fi path
- "Future upgrade: add a Wi-Fi module for cloud telemetry and web dashboards, while preserving local-first safety control."

### 4:45-5:00 | Close
- Summarize: real-time IoT + local reliability + measurable evidence + scalable cloud-ready design.

## Backup plan (if live trigger fails)
- Use existing timeline entries from `data/event_timeline.csv`.
- Use generated evidence summary from `docs/EVENT_EVIDENCE.md`.
- Keep a short screen recording as optional fallback proof.
