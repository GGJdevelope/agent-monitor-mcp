from typing import List, Optional, Any
from fastmcp import FastMCP
from app.models.status import AgentStatus, StatusEvent, AgentState
from app.services.status_service import StatusService
from app.bootstrap import bootstrap_service

mcp = FastMCP("Agent Monitor")

_status_service: Optional[StatusService] = None


def get_service() -> StatusService:
    global _status_service
    if _status_service is None:
        _status_service = bootstrap_service()
    return _status_service


@mcp.tool()
async def report_status(
    agent_id: str,
    run_id: str,
    task_name: str,
    status: str,
    progress: int = 0,
    message: Optional[str] = None,
    metadata: Optional[Any] = None,
    instance_id: Optional[str] = None,
    branch: Optional[str] = None,
    working_dir: Optional[str] = None,
) -> str:
    """Report the current status of an agent task."""
    try:
        # Validate status enum
        agent_status = AgentStatus(status.lower())
    except ValueError:
        return f"Error: Invalid status '{status}'. Must be one of: {[s.value for s in AgentStatus]}"

    event = StatusEvent(
        instance_id=instance_id,
        agent_id=agent_id,
        run_id=run_id,
        task_name=task_name,
        status=agent_status,
        progress=progress,
        message=message,
        metadata=metadata or {},
        branch=branch,
        working_dir=working_dir,
    )

    get_service().update_status(event)
    return f"Status updated for agent {agent_id} (instance: {event.instance_id})"


@mcp.tool()
async def get_all_status() -> List[AgentState]:
    """Get the current status of all agents."""
    return get_service().get_all_agent_states()


@mcp.tool()
async def get_agent_status(instance_id: str) -> Optional[AgentState]:
    """Get the current status of a specific agent instance."""
    return get_service().get_agent_state(instance_id)


if __name__ == "__main__":
    # Eagerly bootstrap on actual MCP server process startup
    get_service()
    mcp.run()
