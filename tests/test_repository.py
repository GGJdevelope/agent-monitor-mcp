from datetime import datetime, timezone, timedelta
from app.models.status import StatusEvent, AgentStatus, AgentState


def test_add_and_get_event(repository):
    event = StatusEvent(
        instance_id="inst-1",
        agent_id="test-agent",
        run_id="run-1",
        task_name="test-task",
        status=AgentStatus.RUNNING,
        progress=10,
        message="Starting up",
    )
    repository.add_event(event)

    events = repository.get_events("inst-1")
    assert len(events) == 1
    assert events[0].status == AgentStatus.RUNNING
    assert events[0].message == "Starting up"


def test_snapshot_updates(repository):
    event1 = StatusEvent(
        instance_id="inst-1",
        agent_id="test-agent",
        run_id="run-1",
        task_name="test-task",
        status=AgentStatus.RUNNING,
        progress=10,
    )
    event2 = StatusEvent(
        instance_id="inst-1",
        agent_id="test-agent",
        run_id="run-1",
        task_name="test-task",
        status=AgentStatus.RUNNING,
        progress=50,
    )
    repository.add_event(event1)
    repository.add_event(event2)

    snapshot = repository.get_snapshot("inst-1")
    assert snapshot.progress == 50
    assert snapshot.agent_id == "test-agent"
    assert snapshot.instance_id == "inst-1"


def test_prune_expired_data(repository):
    # Setup: 2 events for agent-1, 1 event for agent-2
    # agent-1 event-1: 10 seconds ago
    # agent-1 event-2: now
    # agent-2 event-1: 20 seconds ago

    now = datetime.now(timezone.utc)
    old_time_10s = now - timedelta(seconds=10)
    old_time_20s = now - timedelta(seconds=20)

    # Manually insert old events
    with repository._get_connection() as conn:
        # Agent 1 - older event
        conn.execute(
            "INSERT INTO agent_status_events (instance_id, agent_id, run_id, task_name, status, progress, message, reported_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "inst-1",
                "agent-1",
                "run-1",
                "task-1",
                "running",
                10,
                "old",
                old_time_10s.isoformat(),
                "{}",
            ),
        )
        # Agent 2 - very old event
        conn.execute(
            "INSERT INTO agent_status_events (instance_id, agent_id, run_id, task_name, status, progress, message, reported_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "inst-2",
                "agent-2",
                "run-2",
                "task-2",
                "running",
                20,
                "very-old",
                old_time_20s.isoformat(),
                "{}",
            ),
        )

        # Insert current status manually to control updated_at
        conn.execute(
            "INSERT INTO agent_current_status (instance_id, agent_id, run_id, task_name, status, progress, message, reported_at, first_seen_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "inst-1",
                "agent-1",
                "run-1",
                "task-1",
                "running",
                10,
                "old",
                old_time_10s.isoformat(),
                old_time_10s.isoformat(),
                now.isoformat(),
                "{}",
            ),
        )
        conn.execute(
            "INSERT INTO agent_current_status (instance_id, agent_id, run_id, task_name, status, progress, message, reported_at, first_seen_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "inst-2",
                "agent-2",
                "run-2",
                "task-2",
                "running",
                20,
                "very-old",
                old_time_20s.isoformat(),
                old_time_20s.isoformat(),
                old_time_20s.isoformat(),
                "{}",
            ),
        )
        conn.commit()

    # Before prune:
    assert len(repository.get_events("inst-1")) == 1
    assert len(repository.get_events("inst-2")) == 1
    assert repository.get_snapshot("inst-1") is not None
    assert repository.get_snapshot("inst-2") is not None

    # Prune with 15s retention
    cutoff = now - timedelta(seconds=15)
    results = repository.prune_expired_data(cutoff)
    assert results["deleted_events"] == 1
    assert results["deleted_snapshots"] == 1

    assert len(repository.get_events("inst-1")) == 1
    assert len(repository.get_events("inst-2")) == 0
    assert repository.get_snapshot("inst-1") is not None
    assert repository.get_snapshot("inst-2") is None


def test_prune_boundary_cutoff(repository):
    # Define a fixed "now"
    fixed_now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    # Exactly at cutoff (will be kept because we use strictly older <)
    cutoff_time = fixed_now - timedelta(seconds=10)

    with repository._get_connection() as conn:
        conn.execute("DELETE FROM agent_status_events")
        conn.execute(
            "INSERT INTO agent_status_events (instance_id, agent_id, run_id, task_name, status, progress, message, reported_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "inst-b",
                "agent-b",
                "run-b",
                "task-b",
                "running",
                10,
                "boundary",
                cutoff_time.isoformat(),
                "{}",
            ),
        )
        conn.commit()

    results = repository.prune_expired_data(cutoff_time)

    assert results["deleted_events"] == 0
    assert len(repository.get_events("inst-b")) == 1

    # Now test strictly older
    older_time = cutoff_time - timedelta(microseconds=1)
    with repository._get_connection() as conn:
        conn.execute("DELETE FROM agent_status_events")
        conn.execute(
            "INSERT INTO agent_status_events (instance_id, agent_id, run_id, task_name, status, progress, message, reported_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "inst-old",
                "agent-old",
                "run-old",
                "task-old",
                "running",
                10,
                "older",
                older_time.isoformat(),
                "{}",
            ),
        )
        conn.commit()

    results = repository.prune_expired_data(cutoff_time)

    assert results["deleted_events"] == 1
    assert len(repository.get_events("inst-old")) == 0


def test_prune_disabled(repository):
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(seconds=100)

    with repository._get_connection() as conn:
        conn.execute(
            "INSERT INTO agent_status_events (instance_id, agent_id, run_id, task_name, status, progress, message, reported_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "inst-d",
                "agent-d",
                "run-d",
                "task-d",
                "running",
                10,
                "old",
                old_time.isoformat(),
                "{}",
            ),
        )
        conn.commit()

    results = repository.prune_expired_data(now - timedelta(seconds=200))
    assert results["deleted_events"] == 0
    assert len(repository.get_events("inst-d")) == 1


def test_defensive_instance_id_synthesis(repository):
    # Test that add_event synthesizes instance_id if missing
    event = StatusEvent(
        agent_id="agent-s",
        run_id="run-s",
        task_name="task-s",
        status=AgentStatus.RUNNING,
        progress=10,
    )
    # instance_id is Optional and defaults to None
    assert event.instance_id is None

    repository.add_event(event)

    # It should be synthesized as agent_id:run_id
    expected_id = "agent-s:run-s"
    snapshot = repository.get_snapshot(expected_id)
    assert snapshot is not None
    assert snapshot.agent_id == "agent-s"
    assert snapshot.run_id == "run-s"

    events = repository.get_events(expected_id)
    assert len(events) == 1
    assert events[0].instance_id == expected_id


def test_location_label_compact(repository):
    state = AgentState(
        instance_id="inst-1",
        agent_id="agent-1",
        run_id="run-1",
        task_name="task-1",
        status=AgentStatus.RUNNING,
        progress=10,
        reported_at=datetime.now(timezone.utc),
        first_seen_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        working_dir="/Users/user/projects/agent-monitor-mcp",
    )
    # Should show last two components
    assert (
        state.location_label == "projects/agent-monitor-mcp"
        or state.location_label == "projects\\agent-monitor-mcp"
    )

    state.working_dir = "/tmp/test"
    assert state.location_label == "tmp/test" or state.location_label == "tmp\\test"

    state.working_dir = "relative/path"
    assert (
        state.location_label == "relative/path"
        or state.location_label == "relative\\path"
    )

    state.working_dir = "/single"
    assert state.location_label == "single"
