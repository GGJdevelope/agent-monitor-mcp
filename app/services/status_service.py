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
        self._normalize_event(event)
        self.repository.add_event(event)
        return self.get_agent_state(event.instance_id)

    def _normalize_event(self, event: StatusEvent):
        """Normalizes and fills missing fields in the status event."""
        # 1. Synthesize instance_id if missing: agent_id + run_id
        if not event.instance_id:
            event.instance_id = f"{event.agent_id}:{event.run_id}"

        # 2. Try to extract branch from metadata if missing
        if not event.branch and "branch" in event.metadata:
            event.branch = str(event.metadata["branch"])

        # 3. Try to extract working_dir from metadata if missing
        if not event.working_dir and "working_dir" in event.metadata:
            event.working_dir = str(event.metadata["working_dir"])

    def get_agent_state(self, instance_id: str) -> Optional[AgentState]:
        """Returns the current snapshot for a given agent instance, derived for staleness."""
        state = self.repository.get_snapshot(instance_id)
        if not state:
            return None
        return self._apply_stale_check(state)

    def get_all_agent_states(self) -> List[AgentState]:
        """Returns current snapshots for all agent instances."""
        states = self.repository.get_all_snapshots()
        return [self._apply_stale_check(state) for state in states]

    def get_history(self, instance_id: str, limit: int = 100) -> List[StatusEvent]:
        """Returns the history of events for an agent instance."""
        return self.repository.get_events(instance_id, limit)

    def _apply_stale_check(self, state: AgentState) -> AgentState:
        """Marks agent as stale if no update for threshold seconds."""
        # Only mark as STALE if it's not already in a terminal state (COMPLETED, FAILED, CANCELLED)
        if state.status in [
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
        ]:
            return state

        now = datetime.now(timezone.utc)
        if (now - state.reported_at) > timedelta(seconds=self.stale_threshold_seconds):
            state.status = AgentStatus.STALE
        return state
