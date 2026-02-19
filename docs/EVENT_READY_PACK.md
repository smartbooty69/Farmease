# FarmEase Event Ready Pack

This checklist maps exactly to the requested event deliverables.

## Connectivity rationale (for judges)
- Current prototype has no onboard Wi-Fi module on the controller path.
- Cloud sync is therefore optional/redundant for the event build.
- Adopted approach: local-first dashboard control + Telegram alerts/commands.
- Future-state note: with a Wi-Fi module, telemetry can sync to cloud and web dashboards while local safety control remains primary.

## 1) Measured impact (hard number)
- Source: `docs/EVENT_EVIDENCE.md`
- Current generated examples:
  - Irrigation runtime avoided proxy (%): present
  - Sampling interval and runtime window: present

Generate/refresh:

```powershell
python scripts/generate_event_evidence.py
```

## 2) Reliability proof (4-8 hour style)
- Template: `docs/EVENT_RELIABILITY_LOG_TEMPLATE.md`
- Runtime evidence source: `data/event_timeline.csv`

## 3) Demo script (3-5 min)
- Script: `docs/EVENT_DEMO_SCRIPT.md`
- Includes exact sequence, triggers, expected outcomes, and backup flow.

## 4) Architecture slide
- Diagram + talk track: `docs/EVENT_ARCHITECTURE.md`
- Standalone Mermaid files:
  - `docs/diagrams/system_architecture.mermaid.js`
  - `docs/diagrams/event_demo_sequence.mermaid.js`
  - `docs/diagrams/fallback_control_flow.mermaid.js`

## 5) Result evidence
- Model quality: `models/training_report.json`
- Timeline logs: `data/event_timeline.csv`
- Condensed event evidence: `docs/EVENT_EVIDENCE.md`

## 6) Fallback plan
- Internet/Telegram failure behavior and local-first controls:
  - `docs/EVENT_FALLBACK_PLAN.md`

## 7) One-page presentation assets
- Problem statement, societal relevance, BOM, roadmap:
  - `docs/EVENT_ONE_PAGER.md`

## 8) Ops polish (full rehearsal)
- Rehearsal script: `scripts/event_rehearsal.ps1`
- Run once before event day:

```powershell
.\scripts\event_rehearsal.ps1
```

This has been executed once in this workspace successfully.
