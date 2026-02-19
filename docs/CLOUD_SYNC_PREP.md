# Cloud Sync Prep

## Goal

Send FarmEase event timeline data to a cloud ingest endpoint.

## Required `.env` values

```env
FARMEASE_CLOUD_SYNC=true
FARMEASE_CLOUD_ENDPOINT=http://127.0.0.1:8787/ingest
FARMEASE_CLOUD_API_KEY=demo-key
FARMEASE_CLOUD_TIMEOUT_SECONDS=8
FARMEASE_CLOUD_POLL_SECONDS=8
FARMEASE_CLOUD_BATCH_SIZE=100
FARMEASE_DEVICE_ID=farmease-edge-01
```

## Run one sync cycle

```powershell
.\scripts\run_cloud_sync.ps1 -Once
```

## Run continuous worker

```powershell
.\scripts\run_cloud_sync.ps1
```

## Force worker enabled from CLI

Use this if `.env` has cloud sync disabled:

```powershell
.\scripts\run_cloud_sync.ps1 -Enabled
```

## Sync state file

Worker progress is tracked in:
- `data/.cloud_sync_state.json`

`last_synced_row` controls resume behavior for `data/event_timeline.csv`.
