flowchart TD
    START[Command/Event Arrives] --> INTERNET{Internet available?}

    INTERNET -->|Yes| TELEGRAM{Telegram/API reachable?}
    INTERNET -->|No| LOCAL_ONLY[Operate Local-Only]

    TELEGRAM -->|Yes| REMOTE_CMD[Accept Remote Alert/Command]
    TELEGRAM -->|No| DEGRADED[Remote Channel Degraded]

    REMOTE_CMD --> SAFETY{Safety checks pass?}
    LOCAL_ONLY --> SAFETY
    DEGRADED --> SAFETY

    SAFETY -->|Yes| EXECUTE[Execute on Local Dashboard -> Serial -> Relay]
    SAFETY -->|No| BLOCK[Block action + Log warning]

    EXECUTE --> LOG[Write to event_timeline.csv]
    BLOCK --> LOG
    LOG --> END[System continues monitoring locally]
