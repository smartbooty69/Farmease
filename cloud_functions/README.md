# Cloud Function: ingest -> Firestore

This folder contains a minimal HTTP Cloud Function that accepts the same
ingest payloads used by the local demo and writes them into Firestore.

Files:
- `main.py` — function entrypoint `ingest(request)`.
- `requirements.txt` — Python deps for local testing & deployment.

Environment variables (set in Cloud Function or via `gcloud`):

- `FIREBASE_PROJECT_ID` — your GCP/Firebase project id
- `FIREBASE_SERVICE_ACCOUNT_PATH` — path to service account JSON on the function VM (optional)
- `FIREBASE_COLLECTION` — Firestore collection name (default `ingested_batches`)
- `FARMEASE_CLOUD_API_KEY` — optional bearer key to protect `/ingest` (demo uses `demo-key`)

Note: alternatively you can bypass the HTTP function and run the `scripts/firestore_sync_worker.py`
which uploads rows directly from the device using a service account or application default credentials.

Local testing:

```bash
python -m pip install -r cloud_functions/requirements.txt
functions-framework --target=ingest --debug
```

The function will listen on `http://127.0.0.1:8080/` by default.

Deploy with `gcloud` (example):

```bash
gcloud functions deploy ingest \
  --runtime python310 \
  --trigger-http \
  --region=us-central1 \
  --entry-point=ingest \
  --set-env-vars "FIREBASE_PROJECT_ID=your-project-id,FIREBASE_COLLECTION=ingested_batches,FARMEASE_CLOUD_API_KEY=demo-key"
```

Security notes:
- Prefer using a service account and IAM rather than an open HTTP function.
- If you use `FARMEASE_CLOUD_API_KEY`, keep it secret and rotate regularly.
