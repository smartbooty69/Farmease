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
- Latest (read-only) endpoint: `http://127.0.0.1:8787/latest`

You can override values:

```powershell
.\scripts\run_cloud_api.ps1 -ListenHost "0.0.0.0" -Port 8787 -ApiKey "demo-key"
```

## Verify API is up

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8787/health"
```

## Web dashboard (optional)

Run lightweight web dashboard:

```powershell
.\scripts\run_web_frontend.ps1
```

Default URL:
- `http://127.0.0.1:8080/`

Dashboard JSON feed:
- `http://127.0.0.1:8080/api/dashboard`

The web dashboard is read-only and pulls data from cloud latest endpoint.
Set in `.env`:
- `FARMEASE_CLOUD_ENDPOINT=http://127.0.0.1:8787/ingest` (auto-derives `/latest`)
- or `FARMEASE_CLOUD_READ_ENDPOINT=http://127.0.0.1:8787/latest`

## Ingest storage

Accepted batches are appended as JSON lines in:
- `data/cloud_ingest.jsonl`

## Expose externally (optional)

If you use ngrok or another tunnel, point `.env` `FARMEASE_CLOUD_ENDPOINT` to your public `/ingest` URL and keep API keys aligned.
