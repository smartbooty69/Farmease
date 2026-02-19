# Reliability Run Log Template (4-8 Hours)

## Run metadata
- Date:
- Start time:
- End time:
- Device/port:
- Operator:

## Startup checks
- [ ] `scripts/run_dashboard.ps1` starts successfully
- [ ] Serial connected and receiving data
- [ ] Data rows appended to `data/greenhouse_training_data.csv`
- [ ] Events appended to `data/event_timeline.csv`

## Interval checkpoints (every 30-60 min)
| Time | Dashboard responsive | New telemetry rows | New event rows | Errors observed | Notes |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |

## Fault-handling checks
- [ ] Soil sensor fault event captured (if injected)
- [ ] Alert cooldown behavior observed
- [ ] Control command event captured

## End-of-run summary
- Total runtime (hours):
- Crashes observed: 0 / ____
- Recoveries performed:
- Key evidence files:
  - `data/event_timeline.csv`
  - `docs/EVENT_EVIDENCE.md`
  - `models/training_report.json`

## Sign-off
- Reliability status: Pass / Needs fixes
- Signed by:
