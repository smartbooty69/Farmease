# FarmEase Cloud Sync Prep (Future Wi-Fi Path)

This scaffold keeps current local-first behavior unchanged and adds an optional cloud sync worker.

## Why this exists
- Current event build runs without onboard Wi-Fi module in the controller path.
- Cloud sync is optional/future and should not block local dashboard control.

## Added components
- `integrations/cloud_sync.py` - minimal HTTP cloud sync client.
- `scripts/cloud_sync_worker.py` - resumable worker that uploads new rows from:
  - `data/greenhouse_training_data.csv`
  - `data/event_timeline.csv`
- `scripts/run_cloud_sync.ps1` - PowerShell launcher for the worker.
- `data/.cloud_sync_state.json` - local checkpoint state (auto-generated).

## Environment variables
Add these to `.env` when you are ready:

```dotenv
FARMEASE_CLOUD_SYNC=true
FARMEASE_CLOUD_ENDPOINT=https://your-endpoint.example.com/ingest
FARMEASE_CLOUD_API_KEY=replace-with-secret
FARMEASE_CLOUD_TIMEOUT_SECONDS=8
FARMEASE_CLOUD_POLL_SECONDS=8
FARMEASE_CLOUD_BATCH_SIZE=100
FARMEASE_DEVICE_ID=farmease-edge-01
```

## Run cloud sync
```powershell
.\scripts\run_cloud_sync.ps1
```

For a local demo ingest backend, see:
- `docs/CLOUD_BACKEND_SETUP.md`

When backend is running, open:
- `http://127.0.0.1:8000/dashboard`

## Safety guidance
- Keep relay/safety execution local-first.
- Use cloud for telemetry/history and optional command queue in future.
- If internet fails, dashboard and automation must continue locally.
