---
module: Agent Monitor
date: 2026-03-21
problem_type: integration_issue
component: tooling
symptoms:
  - Operators had to watch the dashboard or poll the API to notice when long-running agent tasks finished
  - A completion event at 100% progress could be reported more than once for the same instance
  - Completion notifications needed branch and working directory context to distinguish parallel agent runs safely
root_cause: missing_tooling
resolution_type: tooling_addition
severity: medium
tags: [telegram, notifications, instance-id, deduplication, status-service, monitoring]
---

# Troubleshooting: Telegram completion notifications with instance-aware deduplication

## Problem

After commit `8bfdcd638abf`, the monitor still had no push channel for task completion. Operators had to keep the dashboard open or poll the API manually to learn when a long-running agent instance had actually finished.

The missing piece was not just Telegram delivery itself. The completion signal had to be emitted from the backend source of truth, require valid branch and working-directory context, and notify at most once per `instance_id` even across repeated `completed` updates or service restarts.

## Environment

- Module: Agent Monitor
- Affected Component: Status service, SQLite repository, and Telegram notification service
- Date: 2026-03-21

## Symptoms

- There was no external completion notification when an agent reached its final successful state
- A naive notification trigger could double-send for repeated `completed` updates on the same instance
- Notifications without `branch` and `working_dir` would be ambiguous when the same `agent_id` was reused across runs

## What Didn't Work

**Attempted Solution 1:** Trigger notifications from dashboard rendering or SSE consumers.
- **Why it failed:** UI-driven delivery is not the source of truth. It would miss headless flows, duplicate behavior across surfaces, and couple delivery to whether the dashboard was open.

**Attempted Solution 2:** Treat any `progress == 100` report as completion.
- **Why it failed:** Agents can report `100` while still `running`. The actual completion boundary is the final transition to `status == completed` at `progress == 100`.

**Attempted Solution 3:** Deduplicate by `agent_id` only or with in-memory state.
- **Why it failed:** `agent_id` is display-only and may repeat across instances. In-memory deduplication would also fail across process restarts.

## Solution

The fix added a dedicated `TelegramNotificationService`, wired notification triggering into `StatusService.update_status()`, and persisted one notification marker per `instance_id` in SQLite.

The implementation introduced three key rules:

1. Notify only when the new event is `completed` and `progress == 100`.
2. Require non-blank `branch` and `working_dir` after normalization/fallback.
3. Reserve the notification atomically in the repository before sending so each `instance_id` notifies at most once.

**Delivery Semantics**:
The repository reserves the notification *before* sending. This ensures **at-most-once attempt** semantics: a Telegram send failure is logged but not retried for that specific instance to avoid potentially noisy duplicates.

**Code changes**:
```python
# app/services/status_service.py
def _check_and_notify_completion(self, event: StatusEvent, previous: Optional[AgentState]):
    if event.status != AgentStatus.COMPLETED or event.progress != 100:
        return

    if previous and previous.status == AgentStatus.COMPLETED and previous.progress >= 100:
        return

    branch = (event.branch or "").strip()
    working_dir = (event.working_dir or "").strip()
    if not branch or not working_dir:
        return

    instance_id = event.instance_id or f"{event.agent_id}:{event.run_id}"
    if self.repository.reserve_completion_notification(instance_id):
        self.notification_service.send_completion_notification(...)
```

```python
# app/repositories/status_repository.py
def reserve_completion_notification(self, instance_id: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    try:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO telegram_completion_notifications (instance_id, sent_at) VALUES (?, ?)",
                (instance_id, now),
            )
            return True
    except sqlite3.IntegrityError:
        return False
```

```python
# app/services/telegram_notification_service.py
class TelegramNotificationService:
    def send_completion_notification(self, ...):
        if not self._is_configured():
            return False
        # Formats and sends HTML message via Telegram Bot API
```

**Configuration updates**:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_PROGRESS_NOTIFY_ENABLED=true
```

**Tests added**:
- `tests/test_service.py` covers completion semantics, inheritance from previous snapshot, restart safety, and duplicate completed events
- `tests/test_repository.py` covers idempotent reservation and cleanup of orphaned notification markers
- `tests/test_telegram_notification_service.py` covers configuration no-op behavior

## Why This Works

The root issue was a missing backend integration, not a dashboard problem. By putting the trigger inside `StatusService`, notifications are emitted where canonical status updates are already normalized and persisted.

This design works because it layers correctness checks in the right order:

1. `update_status()` normalizes the event first, including fallback inheritance of `branch` and `working_dir` from the previous snapshot
2. `_check_and_notify_completion()` enforces the exact completion boundary: `completed` plus `100`
3. `reserve_completion_notification()` uses a database primary key on `instance_id` for restart-safe deduplication
4. `TelegramNotificationService` sends the message only when configuration is present, and failures remain non-fatal to status ingestion

That combination prevents false positives, suppresses duplicate sends, and preserves the instance-aware identity model introduced by the earlier `instance_id` work.

## Prevention

- Keep notification triggering in `StatusService`, not in dashboard JS, SSE clients, or other presentation layers
- Preserve the ordering `normalize -> persist -> reserve/send` so inherited branch/path data is available before notification checks run
- Keep deduplication backed by SQLite, not only in memory, so restart safety is maintained
- Add explicit tests for `running@100 -> completed@100`, repeated `completed@100`, missing branch/path, and snapshot inheritance
- If new terminal statuses are introduced later, review notification semantics at the same time

## Related Issues

- See also: [agent-instance-identity-collision-20260320.md](../database-issues/agent-instance-identity-collision-20260320.md)
- Related plan: [feat-telegram-progress-completion-notification-plan](../../plans/2026-03-21-001-feat-telegram-progress-completion-notification-plan.md)
- Related plan: [feat-instance-aware-dashboard-agent-identity-plan](../../plans/2026-03-20-004-feat-instance-aware-dashboard-agent-identity-plan.md)
