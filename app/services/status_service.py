from typing import Optional, List
from datetime import datetime, timezone, timedelta
from app.models.status import StatusEvent, AgentState, AgentStatus
from app.repositories.status_repository import StatusRepository

class StatusService:
    def __init__(self, repository: StatusRepository, stale_threshold_seconds: int = 60):
        self.repository = repository
        self.stale_threshold_seconds = stale_threshold_seconds

    def update_status(self, event: StatusEvent) -> Optional[AgentState]:
        """Adds a new status event and updates current state."""
        self.repository.add_event(event)
        return self.get_agent_state(event.agent_id)

    def get_agent_state(self, agent_id: str) -> Optional[AgentState]:
        """Returns the current snapshot for a given agent, derived for staleness."""
        state = self.repository.get_snapshot(agent_id)
        if not state:
            return None
        return self._apply_stale_check(state)

    def get_all_agent_states(self) -> List[AgentState]:
        """Returns current snapshots for all agents."""
        states = self.repository.get_all_snapshots()
        return [self._apply_stale_check(state) for state in states]

    def get_history(self, agent_id: str, limit: int = 100) -> List[StatusEvent]:
        """Returns the history of events for an agent."""
        return self.repository.get_events(agent_id, limit)

    def _apply_stale_check(self, state: AgentState) -> AgentState:
        """Marks agent as stale if no update for threshold seconds."""
        # Only mark as STALE if it's not already in a terminal state (COMPLETED, FAILED, CANCELLED)
        if state.status in [AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.CANCELLED]:
            return state
            
        now = datetime.now(timezone.utc)
        if (now - state.reported_at) > timedelta(seconds=self.stale_threshold_seconds):
            state.status = AgentStatus.STALE
        return state
