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

From project root (Linux/macOS):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .

For production deployments, prefer the pinned dependencies:

```bash
python -m pip install -r requirements-locked.txt
```
```

From Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
```

Run apps/scripts (either run the installed console scripts or the `scripts/` launchers):

```bash
# Run installed console script (after `python -m pip install -e .`):
farmease-dashboard

# Or run the project launchers directly in-place (now located in the `scripts/` package):
python -m scripts.dashboard
python -m scripts.train_models
python -m scripts.predict_next
# To use the Telegram helper module: python -m scripts.telegram_notifier
```

Telegram setup:
- See `docs/TELEGRAM_SETUP.md`

Operations runbook:
- See `docs/OPERATIONS.md`

Event prep assets:
- `docs/EVENT_READY_PACK.md` (single checklist for event readiness)
- `docs/EVENT_EVIDENCE.md` (generated evidence summary)
- `docs/EVENT_DEMO_SCRIPT.md` (3-5 minute demo flow)
- `docs/EVENT_ARCHITECTURE.md` (architecture slide diagram)
- `docs/EVENT_FALLBACK_PLAN.md` (internet/Telegram failure plan)
- `docs/EVENT_ONE_PAGER.md` (problem, impact, BOM, roadmap)
- `docs/EVENT_RELIABILITY_LOG_TEMPLATE.md` (4-8 hour reliability checklist)

Optional cloud-sync prep:
- `docs/CLOUD_SYNC_PREP.md`
- `docs/CLOUD_BACKEND_SETUP.md`
- `.\scripts\run_cloud_sync.ps1`
- `.\scripts\run_cloud_api.ps1`

## Validation commands

Local sanity checks:

```powershell
python -m py_compile dashboard.py telegram_notifier.py
python -m unittest discover -s tests -p "test_*.py"
```

Generate event evidence from current logs/models:

```powershell
python scripts/generate_event_evidence.py
```

Run full event rehearsal workflow:

```powershell
.\scripts\event_rehearsal.ps1
```

Run optional cloud sync worker (future path):

```powershell
.\scripts\run_cloud_sync.ps1
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

## Repository maintenance

- Cleanup performed (Feb 2026): removed Python caches and build artifacts; consolidated requirements into `requirements.txt`.
