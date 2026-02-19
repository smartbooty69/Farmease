from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "cloud_sync.db"


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingested_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                device_id TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                received_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ingested_batches_source_time
            ON ingested_batches (source, received_at)
            """)
        conn.commit()
    finally:
        conn.close()


class IngestPayload(BaseModel):
    source: str = Field(min_length=1)
    rows: list[dict[str, Any]]
    row_count: int = Field(ge=0)
    device: str = Field(min_length=1)
    generated_at: int | None = None


app = FastAPI(title="FarmEase Cloud Ingest API", version="1.0.0")

# Serve project static assets (CSS/js) from the app/static directory
static_dir = PROJECT_ROOT / "app" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


DASHBOARD_HTML = """
<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>FarmEase Cloud Dashboard</title>
    <link rel="stylesheet" href="/static/css/farmease-theme.css">
    <style>
        :root { color-scheme: light dark; }
        * { box-sizing: border-box; }
        body {
            font-family: "Segoe UI", Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: var(--cream-light);
            color: var(--text-dark);
        }
        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: end;
            gap: 12px;
            margin-bottom: 14px;
            background-color: var(--deep-teal);
            color: var(--white-soft);
            padding: 12px;
            border-radius: 10px;
        }
        h1 {
            margin: 0;
            font-size: 30px;
            letter-spacing: 0.3px;
        }
        .sub {
            opacity: 0.78;
            margin-top: 4px;
            font-size: 14px;
        }
        .refresh {
            font-size: 13px;
            opacity: 0.75;
            border: 1px solid #64748b66;
            padding: 8px 10px;
            border-radius: 999px;
            white-space: nowrap;
        }
        .dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            margin-right: 6px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 0 3px #10b98133;
        }

        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 12px;
            margin-bottom: 14px;
        }
        .layout {
            display: grid;
            grid-template-columns: 1.25fr 1fr;
            gap: 14px;
        }
        .stack {
            display: grid;
            gap: 14px;
        }
        .card {
            border-radius: 12px;
            padding: 12px;
            background: var(--card-gradient);
            box-shadow: 0 8px 20px rgba(16, 20, 16, 0.06);
            border: 1px solid rgba(31,45,45,0.06);
        }
        .card h3 {
            margin: 0 0 10px 0;
            font-size: 15px;
            letter-spacing: 0.2px;
        }
        .label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            opacity: 0.72;
            margin-bottom: 6px;
        }
        .value {
            font-size: 28px;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 4px;
        }
        .muted {
            opacity: 0.7;
            font-size: 12px;
        }
        .kv {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 10px;
            margin: 8px 0;
            padding-bottom: 6px;
            border-bottom: 1px dashed #64748b44;
            font-size: 14px;
        }
        .kv:last-child { border-bottom: 0; }
        .chart {
            width: 100%;
            height: 150px;
            border: 1px solid #64748b55;
            border-radius: 9px;
            padding: 8px;
            background: #0f172a10;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        th, td {
            border-bottom: 1px solid #64748b44;
            padding: 7px 6px;
            text-align: left;
            vertical-align: top;
        }
        th {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            opacity: 0.78;
            position: sticky;
            top: 0;
            background: #0000000f;
        }
        .table-wrap {
            max-height: 300px;
            overflow: auto;
            border: 1px solid #64748b44;
            border-radius: 8px;
        }
        .pill {
            display: inline-block;
            padding: 3px 9px;
            border: 1px solid #64748b66;
            border-radius: 999px;
            font-size: 11px;
            letter-spacing: 0.2px;
            font-weight: 600;
        }
        .pill-on { background: #10b98122; border-color: #10b98177; }
        .pill-off { background: #ef444422; border-color: #ef444477; }
        .sev-info { background: #3b82f622; border-color: #3b82f677; }
        .sev-warning { background: #f59e0b22; border-color: #f59e0b77; }
        .sev-critical { background: #ef444422; border-color: #ef444477; }
        .status-healthy { color: #10b981; }
        .status-error { color: #ef4444; }
        .nowrap { white-space: nowrap; }

        @media (max-width: 980px) {
            .layout { grid-template-columns: 1fr; }
            .topbar { flex-direction: column; align-items: start; }
        }
    </style>
</head>
<body>
    <div class=\"topbar\">
        <div>
            <h1>FarmEase Cloud Dashboard</h1>
            <div class=\"sub\">Live operations dashboard for telemetry sync, events, relays, and trends</div>
        </div>
        <div class=\"refresh\"><span class=\"dot\"></span><span id=\"lastRefresh\">Waiting for first refresh...</span></div>
    </div>

    <div class=\"kpi-grid\">
        <div class=\"card\"><div class=\"label\">API Status</div><div class=\"value\" id=\"kpiStatus\">--</div><div class=\"muted\" id=\"kpiService\"></div></div>
        <div class=\"card\"><div class=\"label\">Training Rows Synced</div><div class=\"value\" id=\"kpiTrainingRows\">--</div><div class=\"muted\" id=\"kpiTrainingBatches\"></div></div>
        <div class=\"card\"><div class=\"label\">Event Rows Synced</div><div class=\"value\" id=\"kpiEventRows\">--</div><div class=\"muted\" id=\"kpiEventBatches\"></div></div>
        <div class=\"card\"><div class=\"label\">Last Sync</div><div class=\"value nowrap\" id=\"kpiLastSync\">--</div><div class=\"muted\" id=\"kpiLastSource\"></div></div>
    </div>

    <div class=\"layout\">
        <div class=\"stack\">
            <div class=\"card\">
                <h3>Latest Sensor Snapshot</h3>
                <div class=\"kv\"><span>Temperature</span><strong id=\"sTemp\">--</strong></div>
                <div class=\"kv\"><span>Humidity</span><strong id=\"sHum\">--</strong></div>
                <div class=\"kv\"><span>Soil ADC</span><strong id=\"sSoil\">--</strong></div>
                <div class=\"kv\"><span>Light Lux</span><strong id=\"sLight\">--</strong></div>
                <div class=\"muted\" id=\"sensorTs\">timestamp: --</div>
            </div>

            <div class=\"card\">
                <h3>Relay State Snapshot</h3>
                <div class=\"kv\"><span>Fan</span><span id=\"rFan\">--</span></div>
                <div class=\"kv\"><span>Pump</span><span id=\"rPump\">--</span></div>
                <div class=\"kv\"><span>Light</span><span id=\"rLight\">--</span></div>
                <div class=\"kv\"><span>Buzzer</span><span id=\"rBuzzer\">--</span></div>
            </div>

            <div class=\"card\">
                <h3>Recent Event Feed</h3>
                <div class=\"table-wrap\">
                    <table id=\"eventFeed\"><thead><tr><th>Time</th><th>Type</th><th>Severity</th><th>Message</th></tr></thead><tbody></tbody></table>
                </div>
            </div>
        </div>

        <div class=\"stack\">
            <div class=\"card\">
                <h3>Temperature Trend (last 60 points)</h3>
                <svg class=\"chart\" id=\"tempChart\" viewBox=\"0 0 360 150\" preserveAspectRatio=\"none\"></svg>
            </div>
            <div class=\"card\">
                <h3>Light Trend (last 60 points)</h3>
                <svg class=\"chart\" id=\"lightChart\" viewBox=\"0 0 360 150\" preserveAspectRatio=\"none\"></svg>
            </div>
            <div class=\"card\">
                <h3>Latest Batches</h3>
                <div class=\"table-wrap\">
                    <table id=\"batchTable\"><thead><tr><th>Source</th><th>Rows</th><th>Device</th><th>Received</th></tr></thead><tbody></tbody></table>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function getJson(url) {
            const response = await fetch(url, { cache: 'no-store' });
            if (!response.ok) throw new Error(`${url} -> ${response.status}`);
            return response.json();
        }

        function text(id, value) {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        }

        function formatTimestamp(value) {
            if (!value) return '--';
            return String(value).replace('T', ' ').replace('Z', '');
        }

        function boolPill(value) {
            if (value === null || value === undefined || value === '') return '<span class="pill">--</span>';
            const on = String(value) === '1' || String(value).toLowerCase() === 'true';
            return `<span class=\"pill ${on ? 'pill-on' : 'pill-off'}\">${on ? 'ON' : 'OFF'}</span>`;
        }

        function severityPill(value) {
            const safe = String(value || 'info').toLowerCase();
            if (safe === 'critical') return '<span class="pill sev-critical">critical</span>';
            if (safe === 'warning') return '<span class="pill sev-warning">warning</span>';
            return '<span class="pill sev-info">info</span>';
        }

        function renderLineChart(svgId, values) {
            const svg = document.getElementById(svgId);
            if (!svg) return;
            svg.innerHTML = '';
            if (!values || values.length < 2) {
                svg.innerHTML = '<text x="10" y="20" font-size="12">No trend data</text>';
                return;
            }

            const width = 360;
            const height = 150;
            const min = Math.min(...values);
            const max = Math.max(...values);
            const span = max - min || 1;

            const points = values.map((value, index) => {
                const x = (index / (values.length - 1)) * (width - 16) + 8;
                const y = height - (((value - min) / span) * (height - 26) + 12);
                return `${x.toFixed(1)},${y.toFixed(1)}`;
            }).join(' ');

            svg.innerHTML = `
                <line x1=\"8\" y1=\"140\" x2=\"352\" y2=\"140\" stroke=\"currentColor\" stroke-opacity=\"0.25\" />
                <polyline points=\"${points}\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.2\" />
                <text x=\"8\" y=\"12\" font-size=\"11\">max ${max.toFixed(2)}</text>
                <text x=\"8\" y=\"148\" font-size=\"11\">min ${min.toFixed(2)}</text>
            `;
        }

        function renderEventFeed(items) {
            const tbody = document.querySelector('#eventFeed tbody');
            tbody.innerHTML = '';
            if (!items || items.length === 0) {
                const tr = document.createElement('tr');
                tr.innerHTML = '<td colspan="4">No events yet</td>';
                tbody.appendChild(tr);
                return;
            }
            for (const item of items.slice(0, 14)) {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td class=\"nowrap\">${formatTimestamp(item.timestamp)}</td><td>${item.event_type || ''}</td><td>${severityPill(item.severity)}</td><td>${item.message || ''}</td>`;
                tbody.appendChild(tr);
            }
        }

        function renderBatchTable(items) {
            const tbody = document.querySelector('#batchTable tbody');
            tbody.innerHTML = '';
            if (!items || items.length === 0) {
                const tr = document.createElement('tr');
                tr.innerHTML = '<td colspan="4">No batch data yet</td>';
                tbody.appendChild(tr);
                return;
            }
            for (const item of items.slice(0, 14)) {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td><span class=\"pill\">${item.source}</span></td><td>${item.row_count}</td><td>${item.device_id}</td><td class=\"nowrap\">${formatTimestamp(item.received_at)}</td>`;
                tbody.appendChild(tr);
            }
        }

        async function refresh() {
            text('lastRefresh', `Refreshing at ${new Date().toLocaleTimeString()}`);
            try {
                const data = await getJson('/dashboard-data');

                const healthy = data.health.status === 'ok';
                text('kpiStatus', healthy ? 'Healthy' : 'Degraded');
                const statusEl = document.getElementById('kpiStatus');
                if (statusEl) {
                    statusEl.classList.remove('status-healthy', 'status-error');
                    statusEl.classList.add(healthy ? 'status-healthy' : 'status-error');
                }

                text('kpiService', `${data.health.service} | ${formatTimestamp(data.health.time)}`);
                text('kpiTrainingRows', String(data.training.total_rows));
                text('kpiTrainingBatches', `${data.training.batch_count} batches`);
                text('kpiEventRows', String(data.events.total_rows));
                text('kpiEventBatches', `${data.events.batch_count} batches`);
                text('kpiLastSync', formatTimestamp(data.last_sync.received_at));
                text('kpiLastSource', data.last_sync.source ? `source: ${data.last_sync.source}` : 'source: --');

                const latest = data.latest_telemetry || {};
                text('sTemp', latest.temp_c ? `${latest.temp_c} °C` : '--');
                text('sHum', latest.humidity_pct ? `${latest.humidity_pct} %` : '--');
                text('sSoil', latest.soil_adc ?? '--');
                text('sLight', latest.light_lux ?? '--');
                text('sensorTs', `timestamp: ${formatTimestamp(latest.timestamp || '--')}`);

                const relays = data.latest_relays || {};
                document.getElementById('rFan').innerHTML = boolPill(relays.relay_fan);
                document.getElementById('rPump').innerHTML = boolPill(relays.relay_pump);
                document.getElementById('rLight').innerHTML = boolPill(relays.relay_light);
                document.getElementById('rBuzzer').innerHTML = boolPill(relays.relay_buzzer);

                renderEventFeed(data.recent_events || []);
                renderBatchTable(data.recent_batches || []);
                renderLineChart('tempChart', data.trends.temp_c || []);
                renderLineChart('lightChart', data.trends.light_lux || []);
            } catch (error) {
                text('kpiStatus', 'Error');
                text('kpiService', String(error));
                text('lastRefresh', `Refresh failed at ${new Date().toLocaleTimeString()}`);
                const statusEl = document.getElementById('kpiStatus');
                if (statusEl) {
                    statusEl.classList.remove('status-healthy');
                    statusEl.classList.add('status-error');
                }
            }
        }

        refresh();
        setInterval(refresh, 5000);
    </script>
</body>
</html>
"""


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "farmease-cloud-ingest",
        "db": str(DB_PATH.relative_to(PROJECT_ROOT)),
        "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def get_recent_batches(source: str, limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 200))
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, source, device_id, row_count, received_at, payload_json
            FROM ingested_batches
            WHERE source = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (source, safe_limit),
        ).fetchall()
    finally:
        conn.close()

    return [dict(row) for row in rows]


def extract_rows_from_batches(
    batches: list[dict[str, Any]], max_rows: int = 400
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch in reversed(batches):
        try:
            payload = json.loads(batch.get("payload_json") or "{}")
            payload_rows = payload.get("rows") if isinstance(payload, dict) else []
            if isinstance(payload_rows, list):
                rows.extend([item for item in payload_rows if isinstance(item, dict)])
        except Exception:
            continue
    if len(rows) > max_rows:
        return rows[-max_rows:]
    return rows


def parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


@app.get("/dashboard-data")
def dashboard_data() -> dict[str, Any]:
    health_info = health()

    training_batches = get_recent_batches("training_data", limit=80)
    event_batches = get_recent_batches("event_timeline", limit=80)
    all_recent_batches = sorted(
        [
            {
                k: item.get(k)
                for k in ("id", "source", "device_id", "row_count", "received_at")
            }
            for item in (training_batches + event_batches)
        ],
        key=lambda item: item.get("id", 0),
        reverse=True,
    )

    training_rows = extract_rows_from_batches(training_batches, max_rows=600)
    event_rows = extract_rows_from_batches(event_batches, max_rows=240)

    latest_telemetry = training_rows[-1] if training_rows else {}
    latest_relays = {
        "relay_fan": latest_telemetry.get("relay_fan") if latest_telemetry else None,
        "relay_pump": latest_telemetry.get("relay_pump") if latest_telemetry else None,
        "relay_light": (
            latest_telemetry.get("relay_light") if latest_telemetry else None
        ),
        "relay_buzzer": (
            latest_telemetry.get("relay_buzzer") if latest_telemetry else None
        ),
    }

    temp_points = [
        value
        for value in (parse_float(row.get("temp_c")) for row in training_rows)
        if value is not None
    ]
    light_points = [
        value
        for value in (parse_float(row.get("light_lux")) for row in training_rows)
        if value is not None
    ]

    training_total_rows = sum(
        int(batch.get("row_count") or 0) for batch in training_batches
    )
    event_total_rows = sum(int(batch.get("row_count") or 0) for batch in event_batches)

    last_sync = (
        all_recent_batches[0]
        if all_recent_batches
        else {"source": None, "received_at": None}
    )

    recent_events = list(reversed(event_rows[-20:]))

    return {
        "health": health_info,
        "training": {
            "batch_count": len(training_batches),
            "total_rows": training_total_rows,
        },
        "events": {
            "batch_count": len(event_batches),
            "total_rows": event_total_rows,
        },
        "last_sync": {
            "source": last_sync.get("source"),
            "received_at": last_sync.get("received_at"),
        },
        "latest_telemetry": latest_telemetry,
        "latest_relays": latest_relays,
        "recent_events": recent_events,
        "recent_batches": all_recent_batches[:20],
        "trends": {
            "temp_c": temp_points[-60:],
            "light_lux": light_points[-60:],
        },
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML


@app.post("/ingest")
def ingest(
    payload: IngestPayload,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    expected_key = os.getenv("FARMEASE_CLOUD_API_KEY", "").strip()
    if expected_key:
        expected_auth = f"Bearer {expected_key}"
        if authorization != expected_auth:
            raise HTTPException(status_code=401, detail="unauthorized")

    actual_rows = len(payload.rows)
    if payload.row_count != actual_rows:
        raise HTTPException(status_code=400, detail="row_count mismatch")

    received_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO ingested_batches (source, device_id, row_count, received_at, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.source,
                payload.device,
                int(payload.row_count),
                received_at,
                json.dumps(payload.model_dump(), separators=(",", ":")),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "source": payload.source,
        "accepted_rows": payload.row_count,
        "received_at": received_at,
    }


@app.get("/latest/{source}")
def latest(source: str, limit: int = 5) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 50))

    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, source, device_id, row_count, received_at
            FROM ingested_batches
            WHERE source = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (source, safe_limit),
        ).fetchall()
    finally:
        conn.close()

    return {
        "source": source,
        "count": len(rows),
        "items": [dict(row) for row in rows],
    }
