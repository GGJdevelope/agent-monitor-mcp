import logging
import requests
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

def test_telegram_service_no_op_when_disabled(caplog):
    caplog.set_level(logging.INFO)
    svc = TelegramNotificationService(bot_token="token", chat_id="chat", enabled=False)
    # Mock requests to ensure it's not called
    with patch("requests.post") as mock_post:
        result = svc.send_completion_notification(
            agent_id="a", task_name="t", instance_id="i", branch="b", working_dir="d", timestamp=MagicMock()
        )
        assert result is False
        mock_post.assert_not_called()
        assert "Telegram notification skipped" in caplog.text

def test_telegram_service_no_op_when_config_missing(caplog):
    caplog.set_level(logging.INFO)
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
        assert "Telegram notification skipped" in caplog.text

@patch("requests.post")
def test_telegram_service_send_success(mock_post, caplog):
    caplog.set_level(logging.INFO)
    # Mock success response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    svc = TelegramNotificationService(bot_token="test_token", chat_id="test_chat", enabled=True)
    result = svc.send_completion_notification(
        agent_id="my-agent", task_name="my-task", instance_id="my-instance", 
        branch="main", working_dir="/app", timestamp=MagicMock()
    )

    assert result is True
    assert "Sending Telegram notification" in caplog.text
    assert "instance_id=my-instance" in caplog.text
    assert "Successfully sent" in caplog.text

@patch("requests.post")
def test_telegram_service_send_failure(mock_post, caplog):
    caplog.set_level(logging.ERROR)
    # Mock failure response
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Invalid chat id"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
    mock_post.return_value = mock_response

    svc = TelegramNotificationService(bot_token="test_token", chat_id="test_chat", enabled=True)
    result = svc.send_completion_notification(
        agent_id="my-agent", task_name="my-task", instance_id="my-instance", 
        branch="main", working_dir="/app", timestamp=MagicMock()
    )

    assert result is False
    assert "Failed to send Telegram notification (HTTP 400)" in caplog.text
    assert "Invalid chat id" in caplog.text
