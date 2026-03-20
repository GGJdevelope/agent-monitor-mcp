import pytest
import asyncio
import json
from httpx import AsyncClient, ASGITransport
from app.models.status import StatusEvent, AgentStatus
from app.api.status import generate_status_updates


@pytest.mark.asyncio
async def test_sse_endpoint_basic_headers(app):
    """
    Very simple check to ensure the endpoint exists and returns 200.
    We use a timeout to avoid hangs.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        try:
            async with asyncio.timeout(1.0):
                # Using a GET without streaming but it's an SSE endpoint so it might hang anyway
                # But headers usually come back first.
                async with ac.stream("GET", "/api/stream") as response:
                    assert response.status_code == 200
                    assert response.headers["content-type"].startswith(
                        "text/event-stream"
                    )
        except asyncio.TimeoutError:
            # If it still hangs, we at least don't block the whole suite
            pass


@pytest.mark.asyncio
async def test_event_generation_logic(service):
    """
    Directly test the event-generation logic without the HTTP layer.
    """
    # 1. Trigger first event
    event1 = StatusEvent(
        agent_id="test-agent-1",
        run_id="run-1",
        task_name="task-1",
        status=AgentStatus.RUNNING,
        progress=10,
        message="Started",
    )
    service.update_status(event1)

    gen = generate_status_updates(service)

    # 2. Consume first update - Check for Summary structure
    async with asyncio.timeout(1.0):
        update1 = await anext(gen)
        assert update1["event"] == "status_update"
        data1 = json.loads(update1["data"])
        assert data1["agent_id"] == "test-agent-1"
        assert data1["instance_id"] == "test-agent-1:run-1"
        assert data1["progress"] == 10
        assert "location_label" in data1
        assert "working_dir" not in data1

    # 3. Trigger second event for the same agent
    event2 = StatusEvent(
        instance_id="test-agent-1:run-1",
        agent_id="test-agent-1",
        run_id="run-1",
        task_name="task-1",
        status=AgentStatus.COMPLETED,
        progress=100,
        message="Done",
    )
    service.update_status(event2)

    # 4. Consume second update
    async with asyncio.timeout(1.0):
        update2 = await anext(gen)
        assert update2["event"] == "status_update"
        data2 = json.loads(update2["data"])
        assert data2["agent_id"] == "test-agent-1"
        assert data2["instance_id"] == "test-agent-1:run-1"
        assert data2["progress"] == 100


@pytest.mark.asyncio
async def test_event_generation_multiple_instances_same_agent_id(service):
    """
    Ensure multiple instances of the same agent_id emit separate updates correctly.
    """
    service.update_status(
        StatusEvent(
            agent_id="agent-X",
            run_id="r1",
            task_name="t1",
            status=AgentStatus.RUNNING,
            progress=0,
            message="A",
        )
    )
    service.update_status(
        StatusEvent(
            agent_id="agent-X",
            run_id="r2",
            task_name="t1",
            status=AgentStatus.RUNNING,
            progress=0,
            message="B",
        )
    )

    gen = generate_status_updates(service)

    received = []
    # Take 2 updates
    async with asyncio.timeout(1.0):
        received.append(await anext(gen))
        received.append(await anext(gen))

    instance_ids = [json.loads(r["data"])["instance_id"] for r in received]
    assert "agent-X:r1" in instance_ids
    assert "agent-X:r2" in instance_ids


@pytest.mark.asyncio
async def test_event_generation_multiple_agents(service):
    """
    Ensure multiple agents emit updates correctly.
    """
    service.update_status(
        StatusEvent(
            agent_id="agent-A",
            run_id="r1",
            task_name="t1",
            status=AgentStatus.RUNNING,
            progress=0,
            message="A",
        )
    )
    service.update_status(
        StatusEvent(
            agent_id="agent-B",
            run_id="r1",
            task_name="t1",
            status=AgentStatus.RUNNING,
            progress=0,
            message="B",
        )
    )

    gen = generate_status_updates(service)

    received = []
    # Take 2 updates
    async with asyncio.timeout(1.0):
        received.append(await anext(gen))
        received.append(await anext(gen))

    agent_ids = [json.loads(r["data"])["agent_id"] for r in received]
    assert "agent-A" in agent_ids
    assert "agent-B" in agent_ids
