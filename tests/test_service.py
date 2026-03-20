from datetime import datetime, timezone, timedelta
from app.models.status import StatusEvent, AgentStatus


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
