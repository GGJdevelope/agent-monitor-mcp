# Agent Monitor MCP

A hybrid monitoring system for agents with MCP status ingestion, a FastAPI REST API, and a browser dashboard.

<img width="1580" height="459" alt="스크린샷 2026-03-20 오후 9 19 13" src="https://github.com/user-attachments/assets/72aced69-372d-4433-8d23-82bf087e676c" />


## Setup

1. Install dependencies using Poetry:

   ```bash
   poetry install
   ```

2. Configure environment variables (optional):

   ```bash
   cp .env.example .env
   ```

### Telegram Notifications

The monitor can send notifications to a Telegram chat when an agent task completes.

1. Create a bot using [@BotFather](https://t.me/botfather) and get the **Bot Token**.
2. Get your **Chat ID** (you can use [@userinfobot](https://t.me/userinfobot)).
3. Add the following to your `.env` file:
   ```bash
   TELEGRAM_BOT_TOKEN="your_bot_token"
   TELEGRAM_CHAT_ID="your_chat_id"
   TELEGRAM_PROGRESS_NOTIFY_ENABLED=true
   ```

**Completion Conditions:**
A notification is triggered only when:
- Status transitions to `completed`.
- Progress is exactly `100`.
- Both `branch` and `working_dir` are provided (non-blank).
- A notification for that specific `instance_id` hasn't been sent yet.

The system specifically notifies when the final `completed` status is reached at 100% progress. If an agent reports 100% progress while still `running` and later transitions to `completed`, it will notify upon that final transition. It avoids double-notifying if multiple `completed` updates are received for the same instance.

## Running the Server

Start the FastAPI server:

```bash
poetry run python -m app.main
```

The server will be available at `http://localhost:8000`.

- Dashboard: `http://localhost:8000/`
- API docs: `http://localhost:8000/docs/`

## MCP Server

The MCP server is designed for `stdio` transport in the current MVP. You can run it via:

```bash
poetry run python -m app.mcp_server
```

Or configure it in your LLM client (e.g., Claude Desktop) using the command:
`poetry run python -m app.mcp_server`

### OpenCode Configuration

To connect to this MCP server in OpenCode, add the following to your `opencode.json` (or equivalent client config):

```json
{
  "mcpServers": {
    "agent-monitor": {
      "type": "local",
      "command": ["poetry","--directory","/path/to/agent-monitor-mcp", "run", "python", "-m", "app.mcp_server"],
      "enabled": true
    }
  }
}
```

### Available Tools

- `report_status(agent_id, run_id, task_name, status, progress, message, metadata, instance_id=None, branch=None, working_dir=None)`: Updates agent status.
  - `instance_id`: A unique identifier for the agent instance. If omitted, one is synthesized from `agent_id` and `run_id`.
  - `branch`: The current git branch name.
  - `working_dir`: The absolute path to the agent's working directory.
- `get_all_status()`: Returns current snapshots of all agent instances.
- `get_agent_status(instance_id)`: Returns current snapshot of a specific agent instance.

### Recommended Prompt for Primary Agents

Primary or orchestrator agents should instruct subagents to call `report_status` when a task starts, during progress updates, on completion, and on failure. Use canonical lowercase status values: `running`, `completed`, `failed`, `cancelled`, or `queued`.

The orchestrator can use `get_all_status()` or `get_agent_status(instance_id)` to monitor workers.

```markdown
When executing tasks, use the `agent-monitor` MCP server to report your status:
1. Call `report_status` with status="running" when starting.
2. Provide periodic updates with `progress` (0-100) and a `message`.
3. Call `report_status` with status="completed" or "failed" upon finishing.
```

OR

```markdown
## 📊 Status Reporting (Mandatory)

You must use the `agent-monitor` MCP tool to report status for every non-trivial user job. This is mandatory for transparency and orchestration.

1.  **Start:** Immediately call `agent-monitor_report_status` with `status='running'`, `progress=0`, and a clear `message` describing the task.
2.  **Updates:** Send progress updates (0-100) and messages after each major phase, delegation, or every few meaningful steps.
3.  **Stalls:** If a task stalls or awaits user input, report it in the `message` while remaining `status='running'`.
4.  **Finish:** Conclude with `status='completed'` or `status='failed'`.
5.  **Required Fields:** Every call must include `agent_id`, `run_id`, `task_name`, `status`, `progress`, and `message`. 
6.  **Context (Strongly Recommended):** Include `branch` (current git branch) and `working_dir` (absolute path to current directory) to distinguish instances across branches/projects.
```

## Agent Identity & Privacy

The monitor uses an `instance_id` (explicit or synthesized) as the primary key for state and history. This allows the system to distinguish multiple instances of the same `agent_id` (e.g., running on different branches or in different working directories).

### Privacy Boundary

- **Dashboard List & CLI**: Show only `agent_id`, `branch`, and a **compact location label** (the last two path components of `working_dir` where possible, rather than just the basename).
- **Instance Details**: Show the full absolute `working_dir`, `instance_id`, and other metadata.
- **API**: The `/api/agents` list endpoint provides compact summary data (including `location_label`) and excludes full paths; canonical full details live at `/api/agents/instances/{instance_id}`.

## CLI Monitor

To watch agent status from your terminal:

```bash
poetry run python -m cli.monitor --interval 1
```

Options:

- `--once`: Fetch once and exit.
- `--json`: Output raw JSON.
- `--url`: Specify a different API URL.
- `--interval`: Initial polling interval in seconds (default: 2.0).
- `--max-interval`: Maximum polling interval for backoff (default: 60.0).
- `--backoff-factor`: Backoff multiplier when no changes detected (default: 1.5).

The CLI monitor implements an adaptive backoff mechanism. If no semantic status changes are detected between polls, it progressively increases the polling interval up to the `--max-interval`. Any change to an agent's status, progress, or message will immediately reset the interval to the base `--interval`.

## Features

- **Durable Persistence**: SQLite in WAL mode stores both current snapshots and event history.
- **Real-time Updates**: The dashboard uses Server-Sent Events (SSE) for incremental updates.
- **Stale Detection**: Agents that haven't reported in 60 seconds (configurable) are automatically marked as `STALE` in the dashboard and API (unless in a terminal state).
- **Hybrid Interface**: Shared service layer ensures consistency across MCP, REST, and the Web UI.
- **Single-Instance Design**: The current MVP is designed for single-instance `stdio` transport. The service logic is shared but initialized independently for the MCP tool execution and the FastAPI web application to avoid fragile import-time global state.
- **Adaptive CLI Polling**: The CLI monitor uses semantic change detection to back off polling frequency when status is idle.
- **Telegram Notifications**: Optional synchronous Telegram notifications when an agent task completes (100% progress and `completed` status) on a specific branch and working directory.

## Deployment & Production Guidance

### Reverse Proxy Configuration (SSE)

When deploying behind a reverse proxy (like Nginx or Caddy), specific configuration is required to ensure Server-Sent Events (SSE) function correctly:

- **Disable Buffering**: Proxies must not buffer responses. For Nginx, use `proxy_buffering off;` and `proxy_cache off;`.
- **Timeouts**: Ensure the proxy timeout is longer than the expected heartbeat/keep-alive interval.
- **Headers**: The server emits `Content-Type: text/event-stream` and `Cache-Control: no-cache`.

### Public Exposure Constraints

- **No Built-in Authentication**: The API and dashboard have no built-in authentication.
- **Explicit Warning**: **Do not expose this server to the public internet** without an external authentication layer (e.g., Authelia, Google IAP, or basic auth at the proxy level) and TLS encryption.
- **Root-Path Only**: The current MVP is designed and tested for deployment at the root path (`/`). Deployment to a subpath (e.g., `/monitor/`) is not currently supported or tested.

### Persistence Cleanup

The application generates SQLite runtime files in the project root:

- `agent_monitor.db`
- `agent_monitor.db-wal`
- `agent_monitor.db-shm`

These are excluded from version control via `.gitignore`. 

#### Automatic Startup Retention

You can configure automatic cleanup of old data at startup by setting `STATUS_RETENTION_SECONDS` in your `.env` file. 

- If set to a positive integer (e.g., `86400` for 24 hours), the server will prune both event history and current status snapshots strictly older than the cutoff upon initialization.
- Events are pruned based on their `reported_at` timestamp.
- Current status snapshots are pruned based on their `updated_at` timestamp (last seen).
- If set to `0` (default), automatic cleanup is disabled.

#### Manual Reset

To manually reset the system state, stop the server and delete the `.db*` files.

## Limitations & Human Review

As an MVP, this system has several limitations:

- **No Built-in Auth**: Relies on external infrastructure for security.
- **Single-Instance**: Designed for a single-process/single-instance deployment. SSE broadcasting is in-memory and not synchronized across multiple workers or processes.
- **Manual Dashboard Verification**: While core logic and SSE streams are covered by automated tests, the final visual assembly of the dashboard UI requires manual verification.
- **AI-Generated Lifecycle**: The core application lifecycle and repository patterns were scaffolded with AI assistance and have been reviewed for MVP use.

## Testing

Run tests with Poetry:

```bash
poetry run pytest
```
