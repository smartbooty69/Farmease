# Telegram Alerts Setup

## 1) Create a bot
1. In Telegram, open **BotFather**.
2. Send `/newbot` and follow steps.
3. Copy the bot token.

## 2) Get your chat ID
- Send any message to your bot first.
- Open this URL in browser:
  - `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
- Find `chat.id` in the JSON response.

## 3) Set environment variables (Windows PowerShell)
```powershell
$env:TELEGRAM_BOT_TOKEN="<YOUR_BOT_TOKEN>"
$env:TELEGRAM_CHAT_ID="<YOUR_CHAT_ID>"
$env:TELEGRAM_ALERTS="1"
```

Equivalent `.env` example (project root):

```env
TELEGRAM_BOT_TOKEN=<YOUR_BOT_TOKEN>
TELEGRAM_CHAT_ID=<YOUR_CHAT_ID>
TELEGRAM_ALERTS=1
TELEGRAM_COMMANDS=1
TELEGRAM_ALERT_COOLDOWN=180
TELEGRAM_ALERT_TEMP_OFFSET=2
TELEGRAM_ALERT_SOIL_MARGIN=0
TELEGRAM_FLAME_ACTIVE_VALUE=0
TELEGRAM_IR_ACTIVE_VALUE=0
FARMEASE_MODE=advisory
```

Optional tuning:
```powershell
$env:TELEGRAM_ALERT_COOLDOWN="180"
$env:TELEGRAM_ALERT_TEMP_OFFSET="2"
$env:TELEGRAM_ALERT_SOIL_MARGIN="0"
$env:TELEGRAM_COMMANDS="1"
$env:TELEGRAM_FLAME_ACTIVE_VALUE="0"
$env:TELEGRAM_IR_ACTIVE_VALUE="0"
```

For modules that output HIGH when triggered, set active value to `1`.

## 4) Run dashboard
```powershell
python dashboard.py
```

## Alerts currently sent
- Flame detected
- IR motion/intrusion detected
- High temperature (`temp >= threshold_temp_on + TEMP_OFFSET`)
- Soil dry (`soil_adc <= threshold_soil_dry - SOIL_MARGIN`)

All alerts are rate-limited with cooldown to avoid spamming.

## Telegram control commands
After running `dashboard.py`, send these commands to your bot:

- `/status`
- `/risk`
- `/advice`
- `/history`
- `/fan_on` and `/fan_off`
- `/pump_on` and `/pump_off`
- `/light_on` and `/light_off`
- `/buzzer_on` and `/buzzer_off`
- `/automation_on` and `/automation_off`
- `/all_off`
- `/menu`

Hackathon demo tips:
- Start with `/status` then `/advice` to show explainable automation.
- Trigger a sensor event, then use `/history` to show a live timeline.

Notes:
- Commands are accepted only from the configured `TELEGRAM_CHAT_ID`.
- `/help`, `/start`, or `/menu` returns the command list and shows tap buttons keyboard.
- `FARMEASE_MODE` currently labels system mode in Telegram status/startup messages (default: `advisory`); it does not switch automation logic by itself.
