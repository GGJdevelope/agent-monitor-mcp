from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
from app.models.status import StatusEvent, AgentStatus
from app.services.status_service import StatusService


def test_update_status_returns_state(service):
    event = StatusEvent(
        agent_id="agent-service",
        run_id="run-service",
        task_name="test-task",
        status=AgentStatus.RUNNING,
        progress=25,
        message="Running in service",
    )
    state = service.update_status(event)

    assert state.agent_id == "agent-service"
    assert state.instance_id == "agent-service:run-service"  # Normalized
    assert state.status == AgentStatus.RUNNING
    assert state.message == "Running in service"
    assert state.progress == 25


def test_stale_status_derivation(service):
    # Manually set an old reported_at
    old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    event = StatusEvent(
        instance_id="stale-inst",
        agent_id="stale-agent",
        run_id="run-stale",
        task_name="stale-task",
        status=AgentStatus.RUNNING,
        progress=10,
        reported_at=old_time,
    )
    service.update_status(event)

    # Threshold is 60s, so it should be STALE
    state = service.get_agent_state("stale-inst")
    assert state.status == AgentStatus.STALE


def test_terminal_state_not_stale(service):
    # Manually set an old reported_at but with terminal status
    old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    event = StatusEvent(
        instance_id="comp-inst",
        agent_id="completed-agent",
        run_id="run-comp",
        task_name="comp-task",
        status=AgentStatus.COMPLETED,
        progress=100,
        reported_at=old_time,
    )
    service.update_status(event)

    state = service.get_agent_state("comp-inst")
    assert state.status == AgentStatus.COMPLETED  # Stays completed


def test_duplicate_agent_id_separate_instances(service):
    event1 = StatusEvent(
        agent_id="my-agent",
        run_id="run-1",
        task_name="task-1",
        status=AgentStatus.RUNNING,
    )
    event2 = StatusEvent(
        agent_id="my-agent",
        run_id="run-2",
        task_name="task-1",
        status=AgentStatus.RUNNING,
    )
    service.update_status(event1)
    service.update_status(event2)

    states = service.get_all_agent_states()
    assert len(states) == 2
    instance_ids = [s.instance_id for s in states]
    assert "my-agent:run-1" in instance_ids
    assert "my-agent:run-2" in instance_ids

def test_telegram_notification_trigger(repository):
    mock_notifier = MagicMock()
    mock_notifier.enabled = True
    mock_notifier.bot_token = "fake"
    mock_notifier.chat_id = "123"
    mock_notifier._is_configured.return_value = True
    service = StatusService(
        repository=repository,
        notification_service=mock_notifier
    )

    # 1. RUNNING 50% -> No notify
    event1 = StatusEvent(
        agent_id="agent-1",
        run_id="run-1",
        task_name="task-1",
        status=AgentStatus.RUNNING,
        progress=50,
        branch="feat/test",
        working_dir="/tmp/test"
    )
    service.update_status(event1)
    mock_notifier.send_completion_notification.assert_not_called()

    # 2. COMPLETED 100% with branch + working_dir -> Notify
    event2 = StatusEvent(
        agent_id="agent-1",
        run_id="run-1",
        task_name="task-1",
        status=AgentStatus.COMPLETED,
        progress=100,
        branch="feat/test",
        working_dir="/tmp/test"
    )
    service.update_status(event2)
    mock_notifier.send_completion_notification.assert_called_once()
    mock_notifier.send_completion_notification.reset_mock()

    # 3. Repeat COMPLETED 100% -> No notify (already sent)
    service.update_status(event2)
    mock_notifier.send_completion_notification.assert_not_called()

def test_telegram_notification_missing_branch_or_dir(repository):
    mock_notifier = MagicMock()
    mock_notifier._is_configured.return_value = True
    service = StatusService(
        repository=repository,
        notification_service=mock_notifier
    )

    # Missing branch -> No notify
    event1 = StatusEvent(
        agent_id="agent-2",
        run_id="run-2",
        task_name="task-2",
        status=AgentStatus.COMPLETED,
        progress=100,
        branch="",
        working_dir="/tmp/test"
    )
    service.update_status(event1)
    mock_notifier.send_completion_notification.assert_not_called()

    # Missing working_dir -> No notify
    event2 = StatusEvent(
        agent_id="agent-3",
        run_id="run-3",
        task_name="task-3",
        status=AgentStatus.COMPLETED,
        progress=100,
        branch="main",
        working_dir=" "
    )
    service.update_status(event2)
    mock_notifier.send_completion_notification.assert_not_called()

def test_telegram_notification_progress_less_than_100(repository):
    mock_notifier = MagicMock()
    mock_notifier._is_configured.return_value = True
    service = StatusService(
        repository=repository,
        notification_service=mock_notifier
    )

    event = StatusEvent(
        agent_id="agent-4",
        run_id="run-4",
        task_name="task-4",
        status=AgentStatus.COMPLETED,
        progress=99,
        branch="main",
        working_dir="/tmp/test"
    )
    service.update_status(event)
    mock_notifier.send_completion_notification.assert_not_called()

def test_telegram_notification_status_not_completed(repository):
    mock_notifier = MagicMock()
    mock_notifier._is_configured.return_value = True
    service = StatusService(
        repository=repository,
        notification_service=mock_notifier
    )

    event = StatusEvent(
        agent_id="agent-5",
        run_id="run-5",
        task_name="task-5",
        status=AgentStatus.RUNNING,
        progress=100,
        branch="main",
        working_dir="/tmp/test"
    )
    service.update_status(event)
    mock_notifier.send_completion_notification.assert_not_called()

def test_telegram_notification_restart_safety(repository):
    mock_notifier = MagicMock()
    mock_notifier._is_configured.return_value = True
    instance_id = "agent-6:run-6"

    # Mark as reserved in repository manually
    repository.reserve_completion_notification(instance_id)

    service = StatusService(
        repository=repository,
        notification_service=mock_notifier
    )

    event = StatusEvent(
        agent_id="agent-6",
        run_id="run-6",
        task_name="task-6",
        status=AgentStatus.COMPLETED,
        progress=100,
        branch="main",
        working_dir="/tmp/test"
    )
    service.update_status(event)
    # Should not notify because it's already reserved in DB
    mock_notifier.send_completion_notification.assert_not_called()

def test_telegram_notification_previous_progress_100_not_completed(repository):
    mock_notifier = MagicMock()
    mock_notifier._is_configured.return_value = True
    service = StatusService(
        repository=repository,
        notification_service=mock_notifier
    )

    # 1. RUNNING 100% -> No notify
    event1 = StatusEvent(
        agent_id="agent-7",
        run_id="run-7",
        task_name="task-7",
        status=AgentStatus.RUNNING,
        progress=100,
        branch="main",
        working_dir="/tmp/test"
    )
    service.update_status(event1)
    mock_notifier.send_completion_notification.assert_not_called()

    # 2. COMPLETED 100% -> Should notify because status transition is from RUNNING to COMPLETED
    event2 = StatusEvent(
        agent_id="agent-7",
        run_id="run-7",
        task_name="task-7",
        status=AgentStatus.COMPLETED,
        progress=100,
        branch="main",
        working_dir="/tmp/test"
    )
    service.update_status(event2)
    mock_notifier.send_completion_notification.assert_called_once()

def test_telegram_notification_inheritance(repository):
    mock_notifier = MagicMock()
    mock_notifier._is_configured.return_value = True
    service = StatusService(
        repository=repository,
        notification_service=mock_notifier
    )

    # 1. RUNNING with branch/dir
    event1 = StatusEvent(
        agent_id="agent-8",
        run_id="run-8",
        task_name="task-8",
        status=AgentStatus.RUNNING,
        progress=50,
        branch="main",
        working_dir="/tmp/test"
    )
    service.update_status(event1)
    mock_notifier.send_completion_notification.assert_not_called()

    # 2. COMPLETED 100% WITHOUT branch/dir (should inherit)
    event2 = StatusEvent(
        agent_id="agent-8",
        run_id="run-8",
        task_name="task-8",
        status=AgentStatus.COMPLETED,
        progress=100
        # branch and working_dir omitted
    )
    service.update_status(event2)
    mock_notifier.send_completion_notification.assert_called_once()
    args, kwargs = mock_notifier.send_completion_notification.call_args
    assert kwargs['branch'] == "main"
    assert kwargs['working_dir'] == "/tmp/test"
