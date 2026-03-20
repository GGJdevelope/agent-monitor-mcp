from typing import List, Optional, Any
from fastmcp import FastMCP
from app.models.status import AgentStatus, StatusEvent, AgentState
from app.services.status_service import StatusService
from app.repositories.status_repository import StatusRepository
from app.config import settings

mcp = FastMCP("Agent Monitor")

_status_service: Optional[StatusService] = None

def get_service() -> StatusService:
    global _status_service
    if _status_service is None:
        repository = StatusRepository(settings.DATABASE_URL)
        repository._init_db()
        _status_service = StatusService(repository, stale_threshold_seconds=settings.STALE_THRESHOLD_SECONDS)
    return _status_service

@mcp.tool()
async def report_status(
    agent_id: str,
    run_id: str,
    task_name: str,
    status: str,
    progress: int = 0,
    message: Optional[str] = None,
    metadata: Optional[Any] = None
) -> str:
    """Report the current status of an agent task."""
    try:
        # Validate status enum
        agent_status = AgentStatus(status.lower())
    except ValueError:
        return f"Error: Invalid status '{status}'. Must be one of: {[s.value for s in AgentStatus]}"
    
    event = StatusEvent(
        agent_id=agent_id,
        run_id=run_id,
        task_name=task_name,
        status=agent_status,
        progress=progress,
        message=message,
        metadata=metadata or {}
    )
    
    get_service().update_status(event)
    return f"Status updated for agent {agent_id}"

@mcp.tool()
async def get_all_status() -> List[AgentState]:
    """Get the current status of all agents."""
    return get_service().get_all_agent_states()

@mcp.tool()
async def get_agent_status(agent_id: str) -> Optional[AgentState]:
    """Get the current status of a specific agent."""
    return get_service().get_agent_state(agent_id)

if __name__ == "__main__":
    mcp.run()
