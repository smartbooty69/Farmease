from __future__ import annotations

import os
import time
import json
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Any, Tuple


class FirestoreClient:
    def __init__(self) -> None:
        self.project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
        self.sa_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
        self.collection = os.getenv("FIREBASE_COLLECTION", "ingested_batches")
        self._db = None
        self._init()

    def _init(self) -> None:
        if self._db is not None:
            return

        try:
            if firebase_admin._apps:
                self._db = firestore.client()
                return

            if self.sa_path:
                cred = credentials.Certificate(self.sa_path)
                firebase_admin.initialize_app(
                    cred, {"projectId": self.project_id or None}
                )
            else:
                # Use ADC when running on GCP
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(
                    cred, {"projectId": self.project_id or None}
                )

            self._db = firestore.client()
        except Exception:
            self._db = None

    def is_configured(self) -> bool:
        return self._db is not None

    def send(self, payload: dict[str, Any]) -> Tuple[bool, str]:
        if not self.is_configured():
            return False, "not-configured"

        try:
            doc = {
                "source": payload.get("source"),
                "device": payload.get("device"),
                "row_count": int(payload.get("row_count", 0)),
                "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "payload": payload,
            }
            self._db.collection(self.collection).add(doc)
            return True, "ok"
        except Exception as exc:
            return False, f"firestore-error:{str(exc)}"
