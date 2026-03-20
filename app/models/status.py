from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class AgentStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"

class StatusEvent(BaseModel):
    agent_id: str
    run_id: str
    task_name: str
    status: AgentStatus
    progress: int = Field(ge=0, le=100, default=0)
    message: Optional[str] = None
    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentState(BaseModel):
    agent_id: str
    run_id: str
    task_name: str
    status: AgentStatus
    progress: int
    message: Optional[str] = None
    reported_at: datetime
    first_seen_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
