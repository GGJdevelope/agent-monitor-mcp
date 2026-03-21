from unittest.mock import patch, MagicMock
from app.services.telegram_notification_service import TelegramNotificationService

def test_telegram_service_constructor_defaults():
    with patch("app.services.telegram_notification_service.settings") as mock_settings:
        mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
        mock_settings.TELEGRAM_CHAT_ID = "test_chat"
        mock_settings.TELEGRAM_PROGRESS_NOTIFY_ENABLED = True
        
        # Test default constructor picks from settings
        svc = TelegramNotificationService()
        assert svc.bot_token == "test_token"
        assert svc.chat_id == "test_chat"
        assert svc.enabled is True

        # Test explicit override
        svc2 = TelegramNotificationService(enabled=False)
        assert svc2.enabled is False

def test_telegram_service_no_op_when_disabled():
    svc = TelegramNotificationService(bot_token="token", chat_id="chat", enabled=False)
    # Mock requests to ensure it's not called
    with patch("requests.post") as mock_post:
        result = svc.send_completion_notification(
            agent_id="a", task_name="t", instance_id="i", branch="b", working_dir="d", timestamp=MagicMock()
        )
        assert result is False
        mock_post.assert_not_called()

def test_telegram_service_no_op_when_config_missing():
    # Missing token
    svc = TelegramNotificationService(bot_token=None, chat_id="chat", enabled=True)
    with patch("app.services.telegram_notification_service.settings") as mock_settings:
        mock_settings.TELEGRAM_BOT_TOKEN = None
        mock_settings.TELEGRAM_CHAT_ID = "chat"
        mock_settings.TELEGRAM_PROGRESS_NOTIFY_ENABLED = True
        
        # Re-init to pick up mocked settings
        svc = TelegramNotificationService()
        result = svc.send_completion_notification(
            agent_id="a", task_name="t", instance_id="i", branch="b", working_dir="d", timestamp=MagicMock()
        )
        assert result is False
