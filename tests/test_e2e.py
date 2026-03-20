import pytest
import asyncio
import json
from httpx import AsyncClient
from app.models.status import StatusEvent, AgentStatus

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
async def test_sse_streaming(client: AsyncClient, service):
    # Automated SSE testing in a request/response test client often hangs or needs 
    # specific concurrency support. For the MVP, we verify SSE manually or via 
    # integration tests that support long-running connections.
    # We do NOT claim automated coverage for SSE in the plan.
    pytest.skip("SSE automated coverage is not yet implemented in this test suite")

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
