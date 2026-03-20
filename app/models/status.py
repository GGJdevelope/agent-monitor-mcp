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
    instance_id: Optional[str] = None
    agent_id: str
    run_id: str
    task_name: str
    status: AgentStatus
    progress: int = Field(ge=0, le=100, default=0)
    message: Optional[str] = None
    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    branch: Optional[str] = None
    working_dir: Optional[str] = None


class AgentState(BaseModel):
    instance_id: str
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
    branch: Optional[str] = None
    working_dir: Optional[str] = None

    @property
    def location_label(self) -> str:
        """A short label for the location, e.g. compact working_dir basename."""
        if self.working_dir:
            import os

            # Compact location: last two parts if possible, otherwise just basename
            parts = self.working_dir.rstrip(os.sep).split(os.sep)
            if len(parts) >= 2:
                return os.path.join(parts[-2], parts[-1])
            return parts[-1] if parts else "unknown"
        return "unknown"


class AgentSummary(BaseModel):
    instance_id: str
    agent_id: str
    run_id: str
    task_name: str
    status: AgentStatus
    progress: int
    message: Optional[str] = None
    reported_at: datetime
    updated_at: datetime
    branch: Optional[str] = None
    location_label: str
