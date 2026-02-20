from __future__ import annotations

import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error as url_error
from urllib import request as url_request

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="FarmEase Frontend", version="0.1.0")


def _resolve_cloud_latest_url() -> str:
  explicit = (os.getenv("FARMEASE_CLOUD_READ_ENDPOINT", "") or "").strip()
  if explicit:
    return explicit

  ingest = (os.getenv("FARMEASE_CLOUD_ENDPOINT", "") or "").strip()
  if not ingest:
    return ""

  if ingest.endswith("/ingest"):
    return ingest[: -len("/ingest")] + "/latest"
  return ingest.rstrip("/") + "/latest"


def _fetch_cloud_latest(limit: int = 12) -> dict[str, Any]:
  latest_url = _resolve_cloud_latest_url()
  if not latest_url:
    return {"ok": False, "error": "cloud-endpoint-not-configured"}

  timeout_seconds = max(2, int(os.getenv("FARMEASE_CLOUD_TIMEOUT_SECONDS", "8")))
  api_key = (os.getenv("FARMEASE_CLOUD_API_KEY", "") or "").strip()
  separator = "&" if "?" in latest_url else "?"
  url = f"{latest_url}{separator}limit={max(1, min(100, int(limit)))}"

  request = url_request.Request(
    url,
    method="GET",
    headers={
      "Accept": "application/json",
      "X-API-Key": api_key,
    },
  )

  try:
    with url_request.urlopen(request, timeout=timeout_seconds) as response:
      body = response.read().decode("utf-8")
      payload = json.loads(body or "{}")
      if isinstance(payload, dict):
        payload["source_url"] = latest_url
        return payload
      return {"ok": False, "error": "invalid-cloud-response", "source_url": latest_url}
  except url_error.HTTPError as exc:
    return {"ok": False, "error": f"http-{exc.code}", "source_url": latest_url}
  except url_error.URLError:
    return {"ok": False, "error": "network-error", "source_url": latest_url}
  except Exception:
    return {"ok": False, "error": "unexpected-error", "source_url": latest_url}


def _model_ready_flags() -> dict[str, bool]:
  model_dir = Path("models")
  return {
    "regression": (model_dir / "light_forecast_model.joblib").exists(),
    "classification": (model_dir / "relay_light_model.joblib").exists(),
    "feature_columns": (model_dir / "feature_columns.json").exists(),
  }


def _parse_event_timestamp(value: Any) -> datetime | None:
  if not isinstance(value, str) or not value.strip():
    return None

  text = value.strip()
  if text.endswith("Z"):
    text = text[:-1] + "+00:00"

  try:
    parsed = datetime.fromisoformat(text)
  except Exception:
    return None

  if parsed.tzinfo is None:
    return parsed.replace(tzinfo=timezone.utc)
  return parsed.astimezone(timezone.utc)


def _compute_event_analytics(events: list[dict[str, Any]]) -> dict[str, Any]:
  severity_counts: dict[str, int] = {}
  type_counts: dict[str, int] = {}
  source_counts: dict[str, int] = {}

  now_utc = datetime.now(timezone.utc)
  bucket_start = (now_utc - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
  hourly_labels: list[str] = []
  hourly_counts: list[int] = []
  bucket_index: dict[str, int] = {}

  for index in range(24):
    point = bucket_start + timedelta(hours=index)
    key = point.strftime("%Y-%m-%d %H:00")
    hourly_labels.append(point.strftime("%H:%M"))
    hourly_counts.append(0)
    bucket_index[key] = index

  for event in events:
    if not isinstance(event, dict):
      continue

    severity = str(event.get("severity") or "unknown").lower()
    event_type = str(event.get("event_type") or "unknown").lower()
    source = str(event.get("source") or "unknown").lower()

    severity_counts[severity] = severity_counts.get(severity, 0) + 1
    type_counts[event_type] = type_counts.get(event_type, 0) + 1
    source_counts[source] = source_counts.get(source, 0) + 1

    timestamp = _parse_event_timestamp(event.get("timestamp"))
    if timestamp is None:
      continue

    bucket_key = timestamp.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:00")
    if bucket_key in bucket_index:
      hourly_counts[bucket_index[bucket_key]] += 1

  return {
    "totals": {
      "events": len(events),
      "severity": severity_counts,
      "event_type": type_counts,
      "source": source_counts,
    },
    "hourly_24h": {
      "labels": hourly_labels,
      "counts": hourly_counts,
    },
  }


def _build_dashboard_payload() -> dict[str, Any]:
  mode = os.getenv("FARMEASE_MODE", "advisory")
  event_limit = max(12, min(100, int(os.getenv("FARMEASE_FRONTEND_EVENT_LIMIT", "100"))))
  cloud = _fetch_cloud_latest(limit=event_limit)
  models = _model_ready_flags()
  recent_events = cloud.get("recent_events") if isinstance(cloud.get("recent_events"), list) else []
  analytics = _compute_event_analytics(recent_events)

  payload: dict[str, Any] = {
    "ok": bool(cloud.get("ok", False)),
    "service": "farmease-frontend",
    "mode": mode,
    "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "models": models,
    "cloud_source": cloud.get("source_url") or _resolve_cloud_latest_url() or None,
    "cloud_error": cloud.get("error") if not cloud.get("ok") else None,
    "cloud": {
      "received_at_utc": cloud.get("received_at_utc"),
      "device_id": cloud.get("device_id"),
      "batch_size": cloud.get("batch_size"),
      "sent_at_epoch": cloud.get("sent_at_epoch"),
      "latest_event": cloud.get("latest_event"),
      "recent_events": recent_events,
    },
    "analytics": analytics,
  }
  return payload


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": "farmease-frontend",
        "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


@app.get("/", response_class=HTMLResponse)
def home() -> str:
  return """
<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>FarmEase Web Dashboard</title>
    <style>
      :root {
        color-scheme: light;
      }
      body {
        font-family: Segoe UI, sans-serif;
        margin: 0;
        padding: 24px;
        background: #f4f7fb;
        color: #1f2937;
      }
      h1 {
        margin: 0;
      }
      .sub {
        margin: 8px 0 20px;
        color: #4b5563;
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
      }
      .card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 12px 14px;
      }
      .label {
        font-size: 12px;
        color: #6b7280;
      }
      .value {
        margin-top: 6px;
        font-size: 20px;
        font-weight: 700;
      }
      .status {
        margin-bottom: 14px;
      }
      .mono {
        font-family: Consolas, monospace;
      }
      .footer {
        margin-top: 16px;
        font-size: 13px;
        color: #4b5563;
      }
      .chart-grid {
        margin-top: 12px;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 12px;
      }
      .chart-wrap {
        position: relative;
        width: 100%;
        height: 260px;
      }
      .chart-wrap canvas {
        max-width: 100%;
      }
      .small {
        font-size: 12px;
      }
    </style>
    <script src=\"https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js\"></script>
  </head>
  <body>
    <h1>FarmEase Web Dashboard</h1>
    <p class=\"sub\">Read-only cloud monitoring view (desktop dashboard remains primary control surface).</p>

    <div class=\"status card\">
      <div><strong>Mode:</strong> <span id=\"mode\">--</span></div>
      <div><strong>Cloud Source:</strong> <span class=\"mono\" id=\"cloud-source\">--</span></div>
      <div><strong>Backend Time (UTC):</strong> <span class=\"mono\" id=\"backend-time\">--</span></div>
      <div><strong>Cloud Status:</strong> <span id=\"cloud-status\">--</span></div>
      <div><strong>Models:</strong>
        reg=<span id=\"m-reg\">--</span>,
        cls=<span id=\"m-cls\">--</span>,
        cols=<span id=\"m-cols\">--</span>
      </div>
    </div>

    <div class=\"grid\">
      <div class=\"card\"><div class=\"label\">Device ID</div><div class=\"value\" id=\"device\">--</div></div>
      <div class=\"card\"><div class=\"label\">Cloud Received</div><div class=\"value\" id=\"received\">--</div></div>
      <div class=\"card\"><div class=\"label\">Batch Size</div><div class=\"value\" id=\"batch\">--</div></div>
      <div class=\"card\"><div class=\"label\">Latest Event Type</div><div class=\"value\" id=\"etype\">--</div></div>
      <div class=\"card\"><div class=\"label\">Latest Severity</div><div class=\"value\" id=\"severity\">--</div></div>
      <div class=\"card\"><div class=\"label\">Latest Source</div><div class=\"value\" id=\"esource\">--</div></div>
    </div>

    <div class=\"card\" style=\"margin-top:12px;\">
      <div class=\"label\">Latest Event Message</div>
      <div class=\"value\" id=\"emsg\" style=\"font-size:16px;\">--</div>
    </div>

    <div class=\"card\" style=\"margin-top:12px;\">
      <div class=\"label\">Analytics (from recent cloud events)</div>
      <div class=\"small\" id=\"analytics-meta\" style=\"margin-top:6px; color:#4b5563;\">--</div>
      <div class=\"chart-grid\">
        <div class=\"chart-wrap\"><canvas id=\"severityChart\"></canvas></div>
        <div class=\"chart-wrap\"><canvas id=\"typeChart\"></canvas></div>
        <div class=\"chart-wrap\" style=\"grid-column: span 2;\"><canvas id=\"hourlyChart\"></canvas></div>
      </div>
    </div>

    <div class=\"card\" style=\"margin-top:12px;\">
      <div class=\"label\">Recent Cloud Events</div>
      <ul id=\"events\" style=\"margin:10px 0 0 18px; padding:0;\"></ul>
    </div>

    <div class=\"footer\">
      API: <a href=\"/api/dashboard\">/api/dashboard</a> • <a href=\"/snapshot\">/snapshot</a> • <a href=\"/health\">/health</a>
    </div>

    <script>
      let severityChart = null;
      let typeChart = null;
      let hourlyChart = null;

      function toEntries(mapObject) {
        const entries = Object.entries(mapObject || {});
        entries.sort((a, b) => b[1] - a[1]);
        return entries;
      }

      function renderAnalytics(analytics) {
        console.log('renderAnalytics called with:', analytics);
        const totals = (analytics || {}).totals || {};
        const severityEntries = toEntries(totals.severity || {});
        const typeEntries = toEntries(totals.event_type || {});
        const hourly = (analytics || {}).hourly_24h || {};

        document.getElementById('analytics-meta').textContent = `Events analyzed: ${totals.events ?? 0}`;

        const severityLabels = severityEntries.map(([name]) => name);
        const severityValues = severityEntries.map(([, count]) => count);
        const typeLabels = typeEntries.map(([name]) => name);
        const typeValues = typeEntries.map(([, count]) => count);

        if (severityChart) severityChart.destroy();
        if (typeChart) typeChart.destroy();
        if (hourlyChart) hourlyChart.destroy();

        try {
          console.log('Creating severity chart with labels:', severityLabels, 'values:', severityValues);
          severityChart = new Chart(document.getElementById('severityChart'), {
          type: 'doughnut',
          data: {
            labels: severityLabels,
            datasets: [{
              label: 'Severity',
              data: severityValues,
              backgroundColor: ['#1f77b4', '#ff7f0e', '#d62728', '#2ca02c', '#9467bd']
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { title: { display: true, text: 'Severity Mix' } }
          }
        });

          console.log('Creating type chart with labels:', typeLabels, 'values:', typeValues);
          typeChart = new Chart(document.getElementById('typeChart'), {
            type: 'bar',
            data: {
              labels: typeLabels,
              datasets: [{
                label: 'Count',
                data: typeValues,
                backgroundColor: '#4f46e5'
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: { title: { display: true, text: 'Event Types' } },
              scales: { y: { beginAtZero: true } }
            }
          });

          console.log('Creating hourly chart with labels:', hourly.labels, 'counts:', hourly.counts);
          hourlyChart = new Chart(document.getElementById('hourlyChart'), {
            type: 'line',
            data: {
              labels: Array.isArray(hourly.labels) ? hourly.labels : [],
              datasets: [{
                label: 'Events per hour',
                data: Array.isArray(hourly.counts) ? hourly.counts : [],
                borderColor: '#059669',
                backgroundColor: 'rgba(5, 150, 105, 0.15)',
                fill: true,
                tension: 0.25
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: { title: { display: true, text: '24h Event Trend' } },
              scales: { y: { beginAtZero: true } }
            }
          });
          console.log('All charts created successfully');
        } catch (chartError) {
          console.error('Chart creation error:', chartError);
        }
          document.getElementById('received').textContent = cloud.received_at_utc || '--';
          document.getElementById('batch').textContent = cloud.batch_size ?? '--';
          document.getElementById('etype').textContent = latestEvent.event_type || '--';
          document.getElementById('severity').textContent = latestEvent.severity || '--';
          document.getElementById('esource').textContent = latestEvent.source || '--';
          document.getElementById('emsg').textContent = latestEvent.message || '--';

          const eventsList = document.getElementById('events');
          eventsList.innerHTML = '';
          const recent = Array.isArray(cloud.recent_events) ? cloud.recent_events : [];
          recent.slice().reverse().forEach((eventItem) => {
            const li = document.createElement('li');
            li.style.marginBottom = '6px';
            const ts = eventItem.timestamp || '--';
            const sev = eventItem.severity || 'info';
            const src = eventItem.source || 'unknown';
            const msg = eventItem.message || '';
            li.textContent = `${ts} [${sev}] ${src}: ${msg}`;
            eventsList.appendChild(li);
          });

          renderAnalytics(payload.analytics || {});
        } catch (error) {
          console.error('Dashboard refresh error:', error);
        }
      }

      refreshDashboard();
      setInterval(refreshDashboard, 3000);
    </script>
  </body>
</html>
"""


@app.get("/api/dashboard")
def api_dashboard() -> JSONResponse:
    payload = _build_dashboard_payload()
    return JSONResponse(payload)


@app.get("/snapshot")
def snapshot() -> JSONResponse:
  try:
    payload = _build_dashboard_payload()
    latest_event = (((payload.get("cloud") or {}).get("latest_event")) or None)
    if latest_event is None:
      return JSONResponse({"ok": False, "error": payload.get("cloud_error", "cloud-data-missing")}, status_code=404)
    return JSONResponse({"ok": True, "latest": latest_event})
  except Exception as exc:
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("FARMEASE_FRONTEND_HOST", "127.0.0.1")
    port = int(os.getenv("FARMEASE_FRONTEND_PORT", "8080"))
    uvicorn.run("cloud_backend.frontend_server:app", host=host, port=port, reload=False)
