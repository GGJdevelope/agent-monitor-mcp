from datetime import datetime, timezone, timedelta
from app.models.status import StatusEvent, AgentStatus, AgentState

def test_update_status_returns_state(service):
    event = StatusEvent(
        agent_id="agent-service",
        run_id="run-service",
        task_name="test-task",
        status=AgentStatus.RUNNING,
        progress=25,
        message="Running in service"
    )
    state = service.update_status(event)
    
    assert state.agent_id == "agent-service"
    assert state.status == AgentStatus.RUNNING
    assert state.message == "Running in service"
    assert state.progress == 25

def test_stale_status_derivation(service):
    # Manually set an old reported_at
    old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    event = StatusEvent(
        agent_id="stale-agent",
        run_id="run-stale",
        task_name="stale-task",
        status=AgentStatus.RUNNING,
        progress=10,
        reported_at=old_time
    )
    service.update_status(event)
    
    # Threshold is 60s, so it should be STALE
    state = service.get_agent_state("stale-agent")
    assert state.status == AgentStatus.STALE

def test_terminal_state_not_stale(service):
    # Manually set an old reported_at but with terminal status
    old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    event = StatusEvent(
        agent_id="completed-agent",
        run_id="run-comp",
        task_name="comp-task",
        status=AgentStatus.COMPLETED,
        progress=100,
        reported_at=old_time
    )
    service.update_status(event)
    
    state = service.get_agent_state("completed-agent")
    assert state.status == AgentStatus.COMPLETED # Stays completed
