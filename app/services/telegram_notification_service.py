import requests
import logging
from typing import Optional
from datetime import datetime
import html
from app.config import settings

logger = logging.getLogger(__name__)

class TelegramNotificationService:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: Optional[bool] = None
    ):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.enabled = enabled if enabled is not None else settings.TELEGRAM_PROGRESS_NOTIFY_ENABLED
        self.timeout = 5

    def _is_configured(self) -> bool:
        return bool(self.enabled and self.bot_token and self.chat_id)

    def send_completion_notification(
        self,
        agent_id: str,
        task_name: str,
        instance_id: str,
        branch: str,
        working_dir: str,
        timestamp: datetime
    ) -> bool:
        if not self._is_configured():
            return False

        message = (
            f"<b>✅ Agent Task Completed</b>\n\n"
            f"<b>Agent:</b> {html.escape(agent_id)}\n"
            f"<b>Task:</b> {html.escape(task_name)}\n"
            f"<b>Branch:</b> {html.escape(branch)}\n"
            f"<b>Directory:</b> <code>{html.escape(working_dir)}</code>\n"
            f"<b>Instance ID:</b> <code>{html.escape(instance_id)}</code>\n"
            f"<b>Time:</b> {timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False
