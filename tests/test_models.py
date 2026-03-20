from datetime import datetime, timezone
from app.models.status import StatusEvent, AgentStatus, AgentState

def test_status_event_validation():
    event = StatusEvent(
        agent_id="test-agent",
        run_id="run-123",
        task_name="test-task",
        status=AgentStatus.RUNNING,
        progress=50,
        message="Running task",
        metadata={"foo": "bar"}
    )
    assert event.agent_id == "test-agent"
    assert event.status == AgentStatus.RUNNING
    assert event.progress == 50
    assert isinstance(event.reported_at, datetime)

def test_agent_state_validation():
    now = datetime.now(timezone.utc)
    state = AgentState(
        agent_id="test-agent",
        run_id="run-123",
        task_name="test-task",
        status=AgentStatus.COMPLETED,
        progress=100,
        reported_at=now,
        first_seen_at=now,
        updated_at=now,
        metadata={"result": "success"}
    )
    assert state.status == AgentStatus.COMPLETED
    assert state.progress == 100
