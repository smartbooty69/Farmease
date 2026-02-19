# FarmEase Fallback Plan (Internet/Telegram Failure)

## Control priorities
1. Local dashboard control (primary)
2. Automation thresholds on local system
3. Telegram/cloud control (secondary)

## If internet is down
- Local serial ingest continues.
- Local relay control continues.
- Telemetry logging to `data/` continues.
- Telegram notifications may fail, but safety logic still runs locally.

## If Telegram API is unavailable
- Continue local monitoring and actuation from dashboard.
- Review `data/event_timeline.csv` for all captured events.
- Announce to judges: "Remote channel degraded, local safety/control unaffected."

## Event-day fallback checklist
- Keep dashboard on local machine connected to Arduino.
- Keep `.env` optional; do not block startup if Telegram token is missing.
- Keep one pre-generated evidence file: `docs/EVENT_EVIDENCE.md`.
- Keep one backup CSV snapshot from latest successful run.
