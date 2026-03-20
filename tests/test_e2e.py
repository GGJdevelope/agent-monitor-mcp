import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from app.models.status import StatusEvent, AgentStatus
from app.config import settings

@pytest.mark.asyncio
async def test_startup_retention_cleanup(db_path):
    """
    Integration test for startup retention cleanup.
    """
    from app.repositories.status_repository import StatusRepository
    from app.bootstrap import bootstrap_service
    
    # 1. Manually prepare database with old data
    repo = StatusRepository(db_path)
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(seconds=100)
    
    with repo._get_connection() as conn:
        conn.execute(
            "INSERT INTO agent_status_events (agent_id, run_id, task_name, status, progress, message, reported_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("old-agent", "run-old", "task-old", "running", 10, "old", old_time.isoformat(), "{}")
        )
        conn.execute(
            "INSERT INTO agent_current_status (agent_id, run_id, task_name, status, progress, message, reported_at, first_seen_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("old-agent", "run-old", "task-old", "running", 10, "old", old_time.isoformat(), old_time.isoformat(), old_time.isoformat(), "{}")
        )
        conn.commit()

    # 2. Configure settings for test (60s retention)
    original_db_url = settings.DATABASE_URL
    original_retention = settings.STATUS_RETENTION_SECONDS
    settings.DATABASE_URL = f"sqlite:///{db_path}"
    settings.STATUS_RETENTION_SECONDS = 60
    
    try:
        # 3. Bootstrap (this should trigger cleanup)
        service = bootstrap_service()
        
        # 4. Verify old data is gone
        assert len(service.repository.get_events("old-agent")) == 0
        assert service.repository.get_snapshot("old-agent") is None
    finally:
        # Restore settings
        settings.DATABASE_URL = original_db_url
        settings.STATUS_RETENTION_SECONDS = original_retention

@pytest.mark.asyncio
async def test_fastapi_lifespan_integration_cleanup(db_path):
    """
    Integration test for FastAPI lifespan cleanup.
    """
    from app.repositories.status_repository import StatusRepository
    from fastapi import FastAPI
    from app.main import lifespan
    from httpx import ASGITransport
    
    # 1. Manually prepare database with old data
    repo = StatusRepository(db_path)
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(seconds=100)
    
    with repo._get_connection() as conn:
        conn.execute(
            "INSERT INTO agent_status_events (agent_id, run_id, task_name, status, progress, message, reported_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("lifespan-agent", "run-1", "task-1", "running", 10, "old", old_time.isoformat(), "{}")
        )
        conn.execute(
            "INSERT INTO agent_current_status (agent_id, run_id, task_name, status, progress, message, reported_at, first_seen_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("lifespan-agent", "run-1", "task-1", "running", 10, "old", old_time.isoformat(), old_time.isoformat(), old_time.isoformat(), "{}")
        )
        conn.commit()

    # 2. Configure settings for test
    original_db_url = settings.DATABASE_URL
    original_retention = settings.STATUS_RETENTION_SECONDS
    settings.DATABASE_URL = f"sqlite:///{db_path}"
    settings.STATUS_RETENTION_SECONDS = 60
    
    try:
        # Create a FRESH app instance with the SAME lifespan
        test_app = FastAPI(lifespan=lifespan)
        
        # 3. Explicitly trigger lifespan events
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test"):
            # If the transport doesn't trigger lifespan, try doing it manually via the context manager
            async with lifespan(test_app):
                # At this point, lifespan has run
                service = test_app.state.status_service
                
                # 4. Verify old data is gone
                assert len(service.repository.get_events("lifespan-agent")) == 0
                assert service.repository.get_snapshot("lifespan-agent") is None
    finally:
        # Restore settings
        settings.DATABASE_URL = original_db_url
        settings.STATUS_RETENTION_SECONDS = original_retention

@pytest.mark.asyncio
async def test_bootstrap_fails_on_sql_error(db_path, monkeypatch):
    """
    Test that bootstrap fails fast when pruning raises a sqlite-related error.
    """
    from app.repositories.status_repository import StatusRepository
    from app.bootstrap import bootstrap_service
    import sqlite3

    def mock_prune_expired_data(self, cutoff):
        raise sqlite3.Error("Simulated SQL error")

    monkeypatch.setattr(StatusRepository, "prune_expired_data", mock_prune_expired_data)

    original_db_url = settings.DATABASE_URL
    original_retention = settings.STATUS_RETENTION_SECONDS
    settings.DATABASE_URL = f"sqlite:///{db_path}"
    settings.STATUS_RETENTION_SECONDS = 60

    try:
        with pytest.raises(sqlite3.Error, match="Simulated SQL error"):
            bootstrap_service()
    finally:
        settings.DATABASE_URL = original_db_url
        settings.STATUS_RETENTION_SECONDS = original_retention

@pytest.mark.asyncio
async def test_api_health(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_e2e_flow(client: AsyncClient, service):
    # 1. Report via service (simulating MCP tool call)
    event = StatusEvent(
        agent_id="e2e-agent",
        run_id="run-1",
        task_name="e2e-task",
        status=AgentStatus.RUNNING,
        progress=20,
        message="Starting e2e"
    )
    service.update_status(event)
    
    # 2. Check REST API
    response = await client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert any(a["agent_id"] == "e2e-agent" for a in data)
    
    # 3. Check specific agent
    response = await client.get("/api/agents/e2e-agent")
    assert response.status_code == 200
    assert response.json()["progress"] == 20

    # 4. Check history
    response = await client.get("/api/agents/e2e-agent/history")
    assert response.status_code == 200
    history = response.json()
    assert len(history) >= 1
    assert history[0]["task_name"] == "e2e-task"

@pytest.mark.asyncio
async def test_agent_not_found(client: AsyncClient):
    response = await client.get("/api/agents/unknown-agent")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_mcp_tool_execution():
    from app.mcp_server import report_status, get_all_status
    # Directly test the tools as async functions
    result = await report_status(
        agent_id="mcp-agent",
        run_id="run-mcp",
        task_name="mcp-task",
        status="running",
        progress=50
    )
    assert "Status updated" in result
    
    states = await get_all_status()
    assert any(s.agent_id == "mcp-agent" for s in states)

@pytest.mark.asyncio
async def test_mcp_invalid_status():
    from app.mcp_server import report_status
    result = await report_status(
        agent_id="bad-agent",
        run_id="run-bad",
        task_name="bad-task",
        status="not-a-real-status"
    )
    assert "Error: Invalid status" in result
