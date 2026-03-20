---
title: feat: Harden MVP monitoring follow-up
type: feat
status: completed
date: 2026-03-20
---

# feat: Harden MVP monitoring follow-up

## Overview

Complete the first post-MVP hardening pass for the agent monitor by closing four known gaps: automated SSE coverage, CLI idle backoff, deployment documentation for SSE/public exposure, and `.gitignore` cleanup for generated SQLite files. This plan focuses on making the current MVP more trustworthy and operationally clearer without changing its core single-instance, stdio-first architecture.

## Problem Statement / Motivation

The current MVP is functional, but the repository explicitly documents unfinished work:

- SSE behavior exists in code but is not automatically covered by tests (`tests/test_e2e.py:50-55`)
- CLI polling remains fixed-interval without idle backoff (`cli/monitor.py:52-68`)
- deployment guidance warns against public exposure but does not yet document SSE reverse-proxy requirements in enough detail (`README.md:65-70`)
- generated SQLite runtime files (`agent_monitor.db`, `agent_monitor.db-wal`, `agent_monitor.db-shm`) are present locally but not covered by the current `.gitignore` rules (`.gitignore:57-63`)

This leaves the plan file with intentionally unchecked criteria, makes local git status noisy, and creates uncertainty around production-like behavior for the browser stream.

## Proposed Solution

Treat this as one bundled hardening issue with four linked workstreams:

1. **SSE automated coverage** — add reliable async tests for stream behavior without hanging the suite
2. **CLI adaptive backoff** — add capped idle backoff with deterministic change detection and reset-on-change behavior
3. **Deployment documentation** — document SSE reverse-proxy needs, public exposure constraints, and supported deployment boundaries
4. **`.gitignore` correction** — ignore the project’s actual runtime SQLite files and note how to clean up already-tracked or already-generated artifacts

This should remain a **MORE**-level issue: concrete enough to implement directly, but narrow enough to avoid a large redesign.

## Technical Considerations

- **SSE contract clarity**: the stream is currently implemented with `StreamingResponse` in `app/api/status.py:32-63`; the follow-up should decide whether to keep that path or adopt FastAPI’s documented SSE primitives for clearer semantics
- **Lifespan-aware async testing**: current test fixtures inject app state manually (`tests/conftest.py:28-37`), which may not fully mirror production startup behavior
- **Change detection correctness**: CLI idle backoff must not reset due to response ordering noise; this may require deterministic API ordering or canonical hashing of returned rows
- **Operational safety**: docs must clearly separate “local MVP works” from “safe to expose publicly,” especially because auth/TLS/origin protections are still externalized to infrastructure
- **Ignore-rule scope**: `.gitignore` should target real runtime artifacts without becoming so broad that it accidentally hides intentional checked-in fixtures later

## System-Wide Impact

- **Interaction graph**: service writes update SQLite, SSE reads poll current state, dashboard consumes EventSource, CLI polls REST. Tightening SSE tests and CLI backoff changes how these observation layers behave under idle and reconnect scenarios.
- **Error propagation**: streaming tests need bounded timeouts so broken generators fail quickly instead of hanging CI. CLI backoff must define how network errors affect retry cadence and user output.
- **State lifecycle risks**: stale derivation is currently read-time only; SSE tests should verify whether stale transitions are observable without new writes, or the docs should explicitly limit that expectation.
- **API surface parity**: browser and CLI should continue to reflect the same read model. If ordering or response shape changes to support backoff/test stability, both surfaces must remain aligned.
- **Integration test scenarios**:
  - stream connection with existing state
  - stream stays alive while idle and emits heartbeat/keep-alive
  - state update after subscription produces one new event, not duplicates
  - unchanged snapshots do not reset CLI backoff
  - generated SQLite files stay out of `git status` after local runs

## Acceptance Criteria

### Functional Requirements

- [x] `tests/test_e2e.py` or dedicated SSE test files add automated coverage for at least one working stream path using async client streaming and bounded reads
- [x] SSE tests verify the endpoint returns an SSE-compatible response and can emit at least one `status_update` frame without hanging
- [x] CLI watch mode implements capped idle backoff with reset-on-change behavior while preserving `--once` and `--json`
- [x] CLI change detection is stable against unchanged snapshots and explicitly defined in code/tests
- [x] `.gitignore` ignores `agent_monitor.db`, `agent_monitor.db-wal`, and `agent_monitor.db-shm` (or an equivalent explicit runtime DB pattern)

### Non-Functional Requirements

- [x] Streaming tests use hard timeouts / bounded reads so CI cannot hang indefinitely on SSE failures
- [x] Deployment docs include reverse-proxy guidance for SSE buffering, timeout, keep-alive/heartbeat expectations, and public exposure constraints
- [x] Docs clearly state whether root-path only deployment is supported or whether subpath/root_path deployment is supported and tested
- [x] Follow-up changes preserve the current single-process / single-instance MVP boundary

### Quality Gates

- [x] `pytest` passes with the expanded SSE/CLI coverage
- [x] README and plan checkbox state are truthful after the follow-up lands
- [x] Human-review notes remain explicit for any AI-generated lifecycle/security-sensitive code paths

## Success Metrics

- The active plan’s currently unchecked SSE/CLI/deployment/git-noise gaps are either completed or explicitly narrowed with honest documentation
- Running the app locally and then `git status` does not show generated SQLite artifacts as untracked noise
- CLI watch mode reduces polling frequency during long idle periods without delaying visible updates after a change
- Test suite can validate key SSE behavior without manual browser verification for the primary happy path

## Dependencies & Risks

### Dependencies

- Existing MVP implementation in:
  - `app/api/status.py`
  - `cli/monitor.py`
  - `README.md`
  - `.gitignore`
  - `tests/conftest.py`
  - `tests/test_e2e.py`
- Existing project dependency stack in `pyproject.toml`

### Risks

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| SSE tests hang or become flaky | Streaming tests are easy to block forever | Use async streaming reads with timeouts and bounded event consumption |
| CLI backoff resets incorrectly | Response ordering changes can look like state changes | Define deterministic ordering or canonical comparison |
| Docs over-promise deployment support | Reverse-proxy guidance may not match current root-path assumptions | Explicitly document supported deployment boundary and defer unsupported cases |
| Overbroad ignore patterns hide useful files | Future committed fixtures or sample DBs could be ignored accidentally | Prefer explicit project runtime DB filenames/paths over blanket `*.db` if possible |

## Open Questions

### Critical

1. Should this follow-up also migrate the SSE endpoint from raw `StreamingResponse` to FastAPI’s documented SSE response type, or just test/document the current implementation?
2. Is deployment behind a URL subpath a supported goal now, or should docs explicitly limit support to root-path deployment?
3. What exactly counts as a CLI “change” for resetting backoff: any payload diff, semantic agent-state diff, or table-visible diff?

### Important

1. Should automated SSE coverage assert exact wire framing, or only event presence/type/data semantics?
2. Should deployment docs include nginx only, or nginx plus Caddy examples?
3. Should `.gitignore` cover only the default `agent_monitor.db*` runtime files, or broader SQLite runtime patterns?

## Documentation Plan

- Update `README.md` with:
  - SSE reverse-proxy requirements
  - explicit public exposure warning
  - supported deployment boundary (root path vs subpath)
  - CLI backoff behavior
  - note on generated SQLite files and local dev cleanup expectations
- Update `docs/plans/2026-03-20-001-feat-hybrid-fastapi-agent-monitor-plan.md` checkboxes after work is complete
- Optionally capture SSE testing/backoff lessons in `docs/solutions/` if a solutions directory is introduced later

## AI-Era Considerations

- Streaming tests and retry logic are exactly the kind of code AI can implement plausibly but subtly wrong, so this follow-up should emphasize deterministic tests and failure-bound timeouts
- Documentation must avoid overstating what was proven automatically versus manually
- Any AI-assisted deployment guidance should be checked against the actual current app behavior, especially around root path assumptions and reverse-proxy buffering/timeouts

## Sources & References

### Internal References

- Current active MVP plan with remaining unchecked items: `docs/plans/2026-03-20-001-feat-hybrid-fastapi-agent-monitor-plan.md:267-289`
- SSE endpoint implementation: `app/api/status.py:32-63`
- CLI fixed-interval polling: `cli/monitor.py:43-69`
- Existing README limitations: `README.md:63-70`
- Current `.gitignore` SQLite rules mismatch: `.gitignore:57-63`
- Skipped SSE automated test: `tests/test_e2e.py:50-55`

### External References

- FastAPI async tests: https://fastapi.tiangolo.com/advanced/async-tests/
- FastAPI SSE tutorial: https://fastapi.tiangolo.com/tutorial/server-sent-events/
- FastAPI custom/streaming responses: https://fastapi.tiangolo.com/advanced/custom-response/
- FastAPI behind a proxy: https://fastapi.tiangolo.com/advanced/behind-a-proxy/
- Starlette requests / `request.is_disconnected()`: https://www.starlette.io/requests/
- Starlette responses: https://www.starlette.io/responses/
- HTTPX async streaming: https://www.python-httpx.org/async/
- HTTPX ASGI transport: https://www.python-httpx.org/advanced/transports/#asgitransport
- nginx proxy module docs: https://nginx.org/en/docs/http/ngx_http_proxy_module.html
- Caddy reverse_proxy docs: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- Caddy server options/timeouts: https://caddyserver.com/docs/caddyfile/options
- AWS Builders’ Library on retries/backoff/jitter: https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
- SQLite WAL docs: https://www.sqlite.org/wal.html
- GitHub Python `.gitignore`: https://github.com/github/gitignore/blob/main/Python.gitignore

### Related Work

- Current implementation commit: `3cbd13b`
- No additional brainstorms, issues, or solutions documents were found for this follow-up work
