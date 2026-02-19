# FarmEase Event Evidence

Generated: 2026-02-19T09:42:11

## Measured impact
- Logged telemetry rows: 2138
- Complete sensor rows: 2102
- Data collection window: 119.23 minutes
- Median sampling interval: 3.00 seconds
- Pump ON ratio: 0.80%
- Estimated irrigation runtime avoided vs always-on baseline: 99.20%

## Reliability evidence
- Total timeline events captured: 21
- Startup events logged: 6
- Sensor fault events captured: 6
- Control command events captured: 2
- Critical alerts captured: 2

## Model evidence
- Training rows used: 2126 / 2138
- Light forecast MAE: 0.07889917288587686
- Light forecast RMSE: 0.2415158309461841
- Relay classifier F1: None
- Relay classifier ROC-AUC: None
- Relay quality gate passed: False

## Notes
- Irrigation runtime avoided is a proxy metric from `relay_pump` duty-cycle.
- Re-run this script before your final presentation to refresh numbers.
