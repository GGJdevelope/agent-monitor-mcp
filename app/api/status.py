import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from app.models.status import AgentState, StatusEvent, AgentStatus
from app.services.status_service import StatusService

router = APIRouter()

def get_service(request: Request) -> StatusService:
    service = getattr(request.app.state, "status_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="Status service not initialized in app state")
    return service

@router.get("/agents", response_model=List[AgentState])
async def list_agents(request: Request):
    return get_service(request).get_all_agent_states()

@router.get("/agents/{agent_id}", response_model=AgentState)
async def get_agent(request: Request, agent_id: str):
    state = get_service(request).get_agent_state(agent_id)
    if not state:
        raise HTTPException(status_code=404, detail="Agent not found")
    return state

@router.get("/agents/{agent_id}/history", response_model=List[StatusEvent])
async def get_agent_history(request: Request, agent_id: str, limit: int = 100):
    return get_service(request).get_history(agent_id, limit=limit)

@router.get("/stream")
async def stream_status(request: Request):
    service = get_service(request)
    return EventSourceResponse(generate_status_updates(service, request))

async def generate_status_updates(service: StatusService, request: Optional[Request] = None):
    # Minimalist SSE polling for SQLite-backed state
    last_seen_updates = {} # agent_id -> updated_at
    
    while True:
        if request and await request.is_disconnected():
            break
            
        current_states = service.get_all_agent_states()
        
        for state in current_states:
            last_updated = last_seen_updates.get(state.agent_id)
            if last_updated is None or state.updated_at > last_updated:
                yield {
                    "event": "status_update",
                    "data": state.model_dump_json()
                }
                last_seen_updates[state.agent_id] = state.updated_at
        
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
