import os
import time
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Request, jsonify, make_response


def _init_firestore():
    if firebase_admin._apps:
        return firestore.client()

    sa_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
    if sa_path:
        cred = credentials.Certificate(sa_path)
    else:
        cred = credentials.ApplicationDefault()

    firebase_admin.initialize_app(cred, {"projectId": os.getenv("FIREBASE_PROJECT_ID")})
    return firestore.client()


def _check_auth(request: Request) -> bool:
    expected_key = os.getenv("FARMEASE_CLOUD_API_KEY", "").strip()
    if not expected_key:
        return True
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {expected_key}"


def ingest(request: Request):
    """HTTP Cloud Function to accept ingest payloads and write to Firestore.

    Expects JSON body with keys: `source`, `rows`, `row_count`, `device`.
    If `FARMEASE_CLOUD_API_KEY` is set in the function environment, a
    matching `Authorization: Bearer <key>` header is required.
    """
    if not _check_auth(request):
        return make_response(jsonify({"error": "unauthorized"}), 401)

    try:
        payload = request.get_json()
    except Exception:
        return make_response(jsonify({"error": "invalid-json"}), 400)

    if not payload or "rows" not in payload:
        return make_response(jsonify({"error": "invalid-payload"}), 400)

    rows = payload.get("rows", [])
    if int(payload.get("row_count", 0)) != len(rows):
        return make_response(jsonify({"error": "row_count-mismatch"}), 400)

    try:
        db = _init_firestore()
        collection = os.getenv("FIREBASE_COLLECTION", "ingested_batches")
        doc = {
            "source": payload.get("source"),
            "device": payload.get("device"),
            "row_count": int(payload.get("row_count", 0)),
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": payload,
        }
        db.collection(collection).add(doc)
    except Exception as exc:
        return make_response(jsonify({"error": "write-failed", "detail": str(exc)}), 500)

    return jsonify({"ok": True, "accepted_rows": len(rows), "received_at": doc["received_at"]})
