from typing import Optional, List
from datetime import datetime, timezone, timedelta
from app.models.status import StatusEvent, AgentState, AgentStatus
from app.repositories.status_repository import StatusRepository
from app.services.telegram_notification_service import TelegramNotificationService


class StatusService:
    def __init__(
        self,
        repository: StatusRepository,
        stale_threshold_seconds: int = 60,
        notification_service: Optional[TelegramNotificationService] = None,
    ):
        self.repository = repository
        self.stale_threshold_seconds = stale_threshold_seconds
        self.notification_service = (
            notification_service or TelegramNotificationService()
        )

    def _normalize_event(self, event: StatusEvent, previous: Optional[AgentState] = None):
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

        # 4. Fallback to previous snapshot if still missing
        if previous:
            if not event.branch and previous.branch:
                event.branch = previous.branch
            if not event.working_dir and previous.working_dir:
                event.working_dir = previous.working_dir
            # Also merge metadata if missing
            for key, value in previous.metadata.items():
                if key not in event.metadata:
                    event.metadata[key] = value

    def update_status(self, event: StatusEvent) -> Optional[AgentState]:
        """Adds a new status event and updates current state."""
        instance_id = event.instance_id or f"{event.agent_id}:{event.run_id}"

        # 1. Capture previous snapshot before update
        previous_snapshot = self.repository.get_snapshot(instance_id)

        # 2. Normalize event (with fallback to previous snapshot)
        self._normalize_event(event, previous_snapshot)

        # 3. Add new event and update current snapshot in repo
        self.repository.add_event(event)

        # 4. Check for completion notification trigger
        self._check_and_notify_completion(event, previous_snapshot)

        return self.get_agent_state(instance_id)

    def _check_and_notify_completion(
        self, event: StatusEvent, previous: Optional[AgentState]
    ):
        """
        Notify completion if status is COMPLETED and progress is 100,
        given branch and working_dir are present, and not previously notified.
        """
        # 1. Base criteria
        if event.status != AgentStatus.COMPLETED or event.progress != 100:
            return

        # 2. Skip if previous snapshot already was COMPLETED @ 100
        if (
            previous
            and previous.status == AgentStatus.COMPLETED
            and previous.progress >= 100
        ):
            return

        # 3. Branch and working_dir presence check (skip if missing/blank)
        branch = (event.branch or "").strip()
        working_dir = (event.working_dir or "").strip()
        if not branch or not working_dir:
            return

        # 4. Atomically reserve notification
        instance_id = event.instance_id or f"{event.agent_id}:{event.run_id}"
        if self.repository.reserve_completion_notification(instance_id):
            # 5. Send notification (failures are non-fatal)
            self.notification_service.send_completion_notification(
                agent_id=event.agent_id,
                task_name=event.task_name,
                instance_id=instance_id,
                branch=branch,
                working_dir=working_dir,
                timestamp=event.reported_at,
            )

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
