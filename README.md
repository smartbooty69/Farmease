# Farmease

Smart greenhouse prototype with:
- desktop dashboard + live serial telemetry,
- Telegram alerts/controls,
- ML training and next-step prediction,
- Arduino firmware for sensor/relay IO.

This repository was reorganized (Feb 2026) and keeps backward-compatible root launchers.

## Project status

Current maturity: **Prototype / Early MVP**

Implemented:
- End-to-end data loop (sensor read -> dashboard -> CSV logs -> model training -> prediction)
- Telegram alerting and command controls
- Baseline training reports and model artifact persistence
- CI syntax + unit test checks
- Expanded ML pipeline/unit coverage (data prep, supervised shaping, split/gate utilities)
- Stability-aware model selection using walk-forward mean/std consistency
- Operations scripts/runbook for dashboard startup and retraining workflow

Still pending for production readiness:
- Broader end-to-end/integration tests (dashboard + serial + Telegram command loop)
- Scheduled retraining/monitoring automation (task scheduler or CI cron + alerting)
- Installer/service packaging for non-developer environments

## Structure

- `app/` - desktop dashboard application logic
- `integrations/` - external integrations (Telegram notifier)
- `ml/` - machine learning pipeline, training, and inference scripts
- `firmware/` - Arduino/IoT firmware
- `docs/` - setup and usage documentation
- `data/` - logged sensor/training CSVs (generated locally)
- `models/` - trained model artifacts and reports
- `tests/` - unit tests

## Quick start

From project root (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-ml.txt
```

Run apps/scripts:

```powershell
python dashboard.py
python train_models.py
python predict_next.py
```

Telegram setup:
- See `docs/TELEGRAM_SETUP.md`

Operations runbook:
- See `docs/OPERATIONS.md`

## Validation commands

Local sanity checks:

```powershell
python -m py_compile dashboard.py telegram_notifier.py
python -m unittest discover -s tests -p "test_*.py"
```

CI runs equivalent checks on each push/PR via:
- `.github/workflows/ci.yml`

## Data and artifact policy

Generated runtime logs are intentionally git-ignored:
- `data/greenhouse_training_data.csv`
- `data/event_timeline.csv`

ML artifacts are generated under `models/`.

## Direct module paths

- Dashboard core: `app/dashboard.py`
- Telegram notifier: `integrations/telegram_notifier.py`
- ML pipeline: `ml/ml_pipeline.py`
- Model training: `ml/train_models.py`
- Next-step prediction: `ml/predict_next.py`
- Firmware sketch: `firmware/iotf.ino`

## Near-term backlog (recommended)

1. Add end-to-end tests for dashboard serial ingest and Telegram command handling.
2. Automate retraining cadence (Task Scheduler/GitHub Actions schedule) with report checks.
3. Package dashboard as a persistent service/installer for operator-friendly deployment.
