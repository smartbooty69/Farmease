from integrations.telegram_notifier import TelegramNotifier
import os

__all__ = ["TelegramNotifier"]


def main() -> None:
    """Minimal CLI to check Telegram notifier configuration.

    This does not send messages. It prints whether the notifier is configured
    based on `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    status = "configured" if notifier.is_configured() else "not configured"
    print(f"Telegram notifier: {status}")
