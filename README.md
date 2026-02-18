# Farmease

Reorganized project layout (Feb 2026) with backwards-compatible root launchers.

## Structure

- `app/` - desktop dashboard application logic
- `integrations/` - external integrations (Telegram notifier)
- `ml/` - machine learning pipeline, training, and inference scripts
- `firmware/` - Arduino/IoT firmware
- `docs/` - setup and usage documentation
- `data/` - logged sensor/training CSVs
- `models/` - trained model artifacts and reports

## Run commands (unchanged)

From project root:

- `python dashboard.py`
- `python train_models.py`
- `python predict_next.py`

These root files are compatibility launchers that call the reorganized modules.

## Direct module paths

- Dashboard core: `app/dashboard.py`
- Telegram notifier: `integrations/telegram_notifier.py`
- ML pipeline: `ml/ml_pipeline.py`
- Model training: `ml/train_models.py`
- Next-step prediction: `ml/predict_next.py`
- Firmware sketch: `firmware/iotf.ino`
- Telegram setup: `docs/TELEGRAM_SETUP.md`
