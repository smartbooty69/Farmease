# FarmEase - Event One Pager

## 1) Problem statement
Greenhouse operators face delayed responses to soil dryness, temperature drift, and safety hazards due to manual monitoring. This causes water inefficiency, crop stress, and higher operational risk.

## 2) Solution summary
FarmEase is a local-first smart greenhouse system that combines:
- Real-time IoT telemetry ingestion from sensors,
- Automated relay control and manual override,
- Safety/event alerts with timeline logging,
- ML-backed forecasting and relay decision support.

Connectivity approach in this prototype:
- No onboard Wi-Fi module is present on the current control hardware.
- Therefore, direct cloud sync is not required for core operation in this version.
- System design intentionally prioritizes local serial control plus Telegram for remote alerts/commands.

If Wi-Fi module is available in a future version:
- Device telemetry can be pushed to cloud (MQTT/HTTPS) for web dashboards and long-term analytics.
- Remote commands can be accepted through a cloud queue but executed only after local safety checks.

## 3) Societal and sustainability relevance
- Supports precision agriculture and resource conservation.
- Reduces unnecessary irrigation runtime through threshold-driven control.
- Improves response to safety risks (fire/motion/sensor anomalies).

## 4) Measured evidence (replace with latest generated numbers)
Source: `docs/EVENT_EVIDENCE.md`
- Telemetry rows logged: ____
- Irrigation runtime avoided proxy: ____%
- Events captured with severity timeline: ____
- Model metrics (MAE/F1/ROC-AUC): ____

## 5) Cost/BOM (prototype level)
- Microcontroller board (Arduino-class)
- Temp/Humidity sensor
- Soil moisture sensor
- Light sensor
- Flame sensor + IR sensor
- 4-channel relay module
- Jumper wires, power supply, enclosure

Estimated prototype budget: low-cost student build (exact vendor-dependent pricing).

## 6) Roadmap
- Add optional cloud sync and hosted web dashboard.
- Add scheduled retraining and automated health checks.
- Add richer reliability testing (8+ hour soak runs, sensor calibration pipeline).
- Package as operator-friendly service/installer.
