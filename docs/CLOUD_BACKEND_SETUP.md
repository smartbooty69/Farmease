# Cloud Backend Setup

## Goal

Run a lightweight ingest API for FarmEase cloud sync batches.

## Start local API

From project root:

```powershell
.\scripts\run_cloud_api.ps1
```

Defaults:
- Host: `127.0.0.1`
- Port: `8787`
- API key: `demo-key`
- Ingest endpoint: `http://127.0.0.1:8787/ingest`
- Health endpoint: `http://127.0.0.1:8787/health`

You can override values:

```powershell
.\scripts\run_cloud_api.ps1 -Host "0.0.0.0" -Port 8787 -ApiKey "demo-key"
```

## Verify API is up

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8787/health"
```

## Ingest storage

Accepted batches are appended as JSON lines in:
- `data/cloud_ingest.jsonl`

## Expose externally (optional)

If you use ngrok or another tunnel, point `.env` `FARMEASE_CLOUD_ENDPOINT` to your public `/ingest` URL and keep API keys aligned.
