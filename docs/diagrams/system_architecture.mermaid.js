flowchart LR
    S[Greenhouse Sensors\nTemp/Humidity/Soil/Light\nFlame + IR] --> A[Arduino Controller]
    A --> R[Relay Module\nFan/Pump/Light/Buzzer]
    A --> C[USB Serial COM]
    A -.->|optional future| WF[Wi-Fi Module]

    C --> D[FarmEase Dashboard\nTkinter + Local Rules]
    D --> T[data/greenhouse_training_data.csv]
    D --> E[data/event_timeline.csv]
    D --> G[Telegram Notifier\nAlerts + Commands]

    T --> M[ML Training\ntrain_models.py]
    M --> P[Model Artifacts\ntraining_report.json + joblib]
    P --> I[Inference\npredict_next.py]

    D --> O[Optional Cloud Sync]
    O --> W[Web Dashboard]
    WF --> O

    classDef local fill:#f4f4f4,stroke:#666,stroke-width:1px;
    class S,A,R,C,D,T,E,M,P,I local;