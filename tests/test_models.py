from datetime import datetime, timezone
from app.models.status import StatusEvent, AgentStatus, AgentState


def test_status_event_validation():
    event = StatusEvent(
        instance_id="inst-1",
        agent_id="test-agent",
        run_id="run-123",
        task_name="test-task",
        status=AgentStatus.RUNNING,
        progress=50,
        message="Running task",
        metadata={"foo": "bar"},
        branch="main",
        working_dir="/tmp",
    )
    assert event.instance_id == "inst-1"
    assert event.agent_id == "test-agent"
    assert event.status == AgentStatus.RUNNING
    assert event.progress == 50
    assert event.branch == "main"
    assert event.working_dir == "/tmp"
    assert isinstance(event.reported_at, datetime)


def test_agent_state_validation():
    now = datetime.now(timezone.utc)
    state = AgentState(
        instance_id="inst-1",
        agent_id="test-agent",
        run_id="run-123",
        task_name="test-task",
        status=AgentStatus.COMPLETED,
        progress=100,
        reported_at=now,
        first_seen_at=now,
        updated_at=now,
        metadata={"result": "success"},
        branch="feat-1",
        working_dir="/home/user/project",
    )
    assert state.instance_id == "inst-1"
    assert state.status == AgentStatus.COMPLETED
    assert state.progress == 100
    assert state.branch == "feat-1"
    assert state.working_dir == "/home/user/project"
