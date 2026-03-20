# Agent Monitor MCP

A hybrid monitoring system for agents with MCP status ingestion, a FastAPI REST API, and a browser dashboard.

## Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

2. Configure environment variables (optional):
   ```bash
   cp .env.example .env
   ```

## Running the Server

Start the FastAPI server:
```bash
python -m app.main
```
The server will be available at `http://localhost:8000`.
- Dashboard: `http://localhost:8000/`
- API docs: `http://localhost:8000/docs/`

## MCP Server

The MCP server is designed for `stdio` transport in the current MVP. You can run it via:
```bash
python -m app.mcp_server
```
Or configure it in your LLM client (e.g., Claude Desktop) using the command:
`python -m app.mcp_server`

### Available Tools
- `report_status(agent_id, run_id, task_name, status, progress, message, metadata)`: Updates agent status.
- `get_all_status()`: Returns current snapshots of all agents.
- `get_agent_status(agent_id)`: Returns current snapshot of a specific agent.

## CLI Monitor

To watch agent status from your terminal:
```bash
python -m cli.monitor --interval 1
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

These are excluded from version control via `.gitignore`. To reset the system state, stop the server and delete these files.

## Limitations & Human Review

As an MVP, this system has several limitations:
- **No Built-in Auth**: Relies on external infrastructure for security.
- **Single-Instance**: Designed for a single-process/single-instance deployment. SSE broadcasting is in-memory and not synchronized across multiple workers or processes.
- **Manual Dashboard Verification**: While core logic and SSE streams are covered by automated tests, the final visual assembly of the dashboard UI requires manual verification.
- **AI-Generated Lifecycle**: The core application lifecycle and repository patterns were scaffolded with AI assistance and have been reviewed for MVP use.

## Testing

Run tests with pytest:
```bash
pytest
```
