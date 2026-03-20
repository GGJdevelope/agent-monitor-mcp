---
module: Agent Monitor
date: 2026-03-20
problem_type: database_issue
component: database
symptoms:
  - Agent states were overwritten when the same agent_id reported from different runs or branches
  - Dashboard and CLI collapsed duplicate agent labels into a single current-state row
  - History and detail lookups could not distinguish separate instances that shared an agent_id
root_cause: logic_error
resolution_type: migration
severity: high
tags: [instance-id, sqlite, status-tracking, dashboard, cli, api]
---

# Troubleshooting: Duplicate `agent_id` state collisions across runs

## Problem

The monitor treated `agent_id` as the unique identity for current status storage and lookups. When the same human-readable label was reused across multiple runs, branches, or working directories, one instance overwrote another and the UI could not show them separately.

This document records the instance-aware identity fix introduced in commit 51e2235 (following the initial retention changes in e5e4f40).

## Environment
- Module: Agent Monitor
- Affected Component: SQLite status repository and instance-aware API/UI surfaces
- Date: 2026-03-20

## Symptoms
- A second agent run with the same `agent_id` replaced the first run's snapshot
- Dashboard rows merged distinct instances that should have appeared separately
- CLI output and change detection treated duplicate labels as one agent
- History/detail routes were ambiguous because they were keyed by `agent_id`

## What Didn't Work

**Attempted Solution 1:** Keep `agent_id` as the primary key and only add more display context.
- **Why it failed:** The overwrite happened in persistence and lookup layers, not just presentation. Extra branch or path data would still collapse into one current-state record while the database key remained `agent_id`.

**Attempted Solution 2:** Keep branch and working directory only as metadata.
- **Why it failed:** Hidden metadata did not change the identity contract used by the repository, API, SSE stream, dashboard map, or CLI fingerprinting.

## Solution

The fix introduced `instance_id` as the canonical identity and migrated the SQLite schema so current snapshots and history are keyed by instance instead of by label. When reporters do not provide `instance_id`, the service synthesizes a stable fallback from `agent_id` and `run_id`.

The API, SSE stream, dashboard, CLI, and MCP reporting tool were updated to use `instance_id` for storage and reconciliation while still showing `agent_id` as the human-readable label.

**Example: Canonical Identity in Service and Repository**
```python
# app/services/status_service.py
def _normalize_event(self, event: StatusEvent):
    # Synthesize instance_id if missing to prevent collisions
    if not event.instance_id:
        event.instance_id = f"{event.agent_id}:{event.run_id}"

# app/repositories/status_repository.py
# CREATE TABLE agent_current_status (
#     instance_id TEXT PRIMARY KEY,
#     agent_id TEXT NOT NULL,
#     run_id TEXT NOT NULL, ...
# );
```

## Why This Works

The root problem was an identity-model bug: `agent_id` was readable but not truly unique. By moving the canonical key to `instance_id`, the system can store and retrieve multiple concurrent rows for the same label without collision. The migration preserves legacy data by backfilling `instance_id = agent_id:run_id`.

Because the same identity is now used consistently in the repository, service, API, SSE, dashboard, and CLI, duplicate labels no longer collapse. Branch and working-directory context became useful only after the storage key stopped overwriting sibling instances.

## Prevention

- Treat human-readable labels as display data, not uniqueness guarantees
- Define one canonical identity field and use it consistently across storage, APIs, streams, and UI state
- Add regression tests for duplicate-label scenarios whenever a read model is keyed by an identifier shown to users
- When evolving a persistence identity contract, include an explicit migration/backfill path instead of silently resetting local data

## Related Issues

- Implementation plan: [feat-instance-aware-dashboard-agent-identity-plan](../../plans/2026-03-20-004-feat-instance-aware-dashboard-agent-identity-plan.md)
- Brainstorm: [dashboard-agent-identity-brainstorm](../../brainstorms/2026-03-20-dashboard-agent-identity-brainstorm.md)
- No other `docs/solutions/` entries were documented yet.
