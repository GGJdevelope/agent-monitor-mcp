from app.models.status import StatusEvent, AgentStatus

def test_add_and_get_event(repository):
    event = StatusEvent(
        agent_id="test-agent",
        run_id="run-1",
        task_name="test-task",
        status=AgentStatus.RUNNING,
        progress=10,
        message="Starting up"
    )
    repository.add_event(event)
    
    events = repository.get_events("test-agent")
    assert len(events) == 1
    assert events[0].status == AgentStatus.RUNNING
    assert events[0].message == "Starting up"

def test_snapshot_updates(repository):
    event1 = StatusEvent(
        agent_id="test-agent",
        run_id="run-1",
        task_name="test-task",
        status=AgentStatus.RUNNING,
        progress=10
    )
    event2 = StatusEvent(
        agent_id="test-agent",
        run_id="run-1",
        task_name="test-task",
        status=AgentStatus.RUNNING,
        progress=50
    )
    repository.add_event(event1)
    repository.add_event(event2)
    
    snapshot = repository.get_snapshot("test-agent")
    assert snapshot.progress == 50
    assert snapshot.agent_id == "test-agent"
