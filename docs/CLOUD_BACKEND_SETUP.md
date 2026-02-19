# FarmEase Cloud Backend Setup (Demo)

This adds a minimal ingest backend for cloud-sync demonstrations.

## Components
- API app: `cloud_backend/app.py`
- Runner script: `scripts/run_cloud_api.ps1`
- Storage: `data/cloud_sync.db` (SQLite)

## Install dependencies
```powershell
pip install fastapi uvicorn
```

## Start API
```powershell
.\scripts\run_cloud_api.ps1
```

Endpoints:
- `GET /health`
- `POST /ingest`
- `GET /latest/{source}?limit=5`
- `GET /dashboard` (live web viewer)
- `GET /dashboard-data` (JSON powering live dashboard)

Open viewer in browser:

```text
http://127.0.0.1:8000/dashboard
```

## Connect sync worker
In `.env` set:

```dotenv
FARMEASE_CLOUD_SYNC=true
FARMEASE_CLOUD_ENDPOINT=http://127.0.0.1:8000/ingest
FARMEASE_CLOUD_API_KEY=demo-key
```

Start worker in another terminal:

```powershell
.\scripts\run_cloud_sync.ps1
```

## Security note
If `FARMEASE_CLOUD_API_KEY` is set in the API process environment, `/ingest` requires `Authorization: Bearer <key>`.
