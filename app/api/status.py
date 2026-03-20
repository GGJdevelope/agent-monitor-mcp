import asyncio
from typing import List, Optional
from fastapi import APIRouter, Request, HTTPException
from sse_starlette.sse import EventSourceResponse
from app.models.status import AgentState, StatusEvent, AgentSummary
from app.services.status_service import StatusService

router = APIRouter()


def get_service(request: Request) -> StatusService:
    service = getattr(request.app.state, "status_service", None)
    if service is None:
        raise HTTPException(
            status_code=500, detail="Status service not initialized in app state"
        )
    return service


def to_summary(state: AgentState) -> AgentSummary:
    """Convert a full AgentState to a compact AgentSummary for lists/SSE."""
    return AgentSummary(
        instance_id=state.instance_id,
        agent_id=state.agent_id,
        run_id=state.run_id,
        task_name=state.task_name,
        status=state.status,
        progress=state.progress,
        message=state.message,
        reported_at=state.reported_at,
        updated_at=state.updated_at,
        branch=state.branch,
        location_label=state.location_label,
    )


@router.get("/agents", response_model=List[AgentSummary])
async def list_agents(request: Request):
    states = get_service(request).get_all_agent_states()
    return [to_summary(s) for s in states]


@router.get("/agents/instances/{instance_id}", response_model=AgentState)
async def get_agent_instance(request: Request, instance_id: str):
    state = get_service(request).get_agent_state(instance_id)
    if not state:
        raise HTTPException(status_code=404, detail="Agent instance not found")
    return state


@router.get("/agents/instances/{instance_id}/history", response_model=List[StatusEvent])
async def get_agent_instance_history(
    request: Request, instance_id: str, limit: int = 100
):
    history = get_service(request).get_history(instance_id, limit=limit)
    if not history:
        # Check if instance even exists
        if not get_service(request).get_agent_state(instance_id):
            raise HTTPException(status_code=404, detail="Agent instance not found")
    return history


@router.get("/agents/{instance_id}", response_model=AgentState)
async def get_agent_legacy(request: Request, instance_id: str):
    """Legacy endpoint supporting either instance_id or agent_id for compatibility."""
    state = get_service(request).get_agent_state(instance_id)
    if not state:
        # Fallback to legacy agent_id match
        all_states = get_service(request).get_all_agent_states()
        for s in all_states:
            if s.agent_id == instance_id:
                return s
        raise HTTPException(status_code=404, detail="Agent not found")
    return state


@router.get("/agents/{instance_id}/history", response_model=List[StatusEvent])
async def get_agent_history_legacy(
    request: Request, instance_id: str, limit: int = 100
):
    """Legacy endpoint supporting either instance_id or agent_id for compatibility."""
    history = get_service(request).get_history(instance_id, limit=limit)
    if not history:
        # Fallback search by agent_id for transition
        all_states = get_service(request).get_all_agent_states()
        for s in all_states:
            if s.agent_id == instance_id:
                return get_service(request).get_history(s.instance_id, limit=limit)
        # If no history and no state, 404
        if not get_service(request).get_agent_state(instance_id):
            raise HTTPException(status_code=404, detail="Agent not found")
    return history


@router.get("/stream")
async def stream_status(request: Request):
    service = get_service(request)
    return EventSourceResponse(generate_status_updates(service, request))


async def generate_status_updates(
    service: StatusService, request: Optional[Request] = None
):
    # Minimalist SSE polling for SQLite-backed state
    last_seen_updates = {}  # instance_id -> updated_at

    while True:
        if request and await request.is_disconnected():
            break

        current_states = service.get_all_agent_states()

        for state in current_states:
            last_updated = last_seen_updates.get(state.instance_id)
            if last_updated is None or state.updated_at > last_updated:
                yield {
                    "event": "status_update",
                    "data": to_summary(state).model_dump_json(),
                }
                last_seen_updates[state.instance_id] = state.updated_at

        # Simple polling loop for MVP
        await asyncio.sleep(0.1)
        # If we are in a test environment (no request), allow breaking out
        if not request:
            # We don't sleep in tests to speed them up or avoid hanging
            # The test will consume only what it needs
            pass


@router.get("/health")
async def health():
    return {"status": "ok"}
