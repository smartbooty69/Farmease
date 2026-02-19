sequenceDiagram
    participant J as Judges
    participant UI as FarmEase Dashboard
    participant MCU as Arduino/Relays
    participant LOG as Event Timeline CSV
    participant TG as Telegram
    participant ML as Training Report

    J->>UI: Start live demo
    UI->>MCU: Read sensor telemetry (serial)
    MCU-->>UI: Temp/Humidity/Soil/Light + safety states
    UI->>LOG: Append telemetry + event records

    J->>UI: Trigger manual light ON/OFF
    UI->>MCU: Relay command
    MCU-->>UI: Relay state updated
    UI->>LOG: Control event saved

    J->>UI: Trigger safety condition
    UI->>TG: Send alert (if internet available)
    UI->>LOG: Save critical/warning event

    J->>ML: Review model metrics
    ML-->>J: MAE, RMSE, F1/ROC-AUC, quality gate