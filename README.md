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

## Features

- **Durable Persistence**: SQLite in WAL mode stores both current snapshots and event history.
- **Real-time Updates**: The dashboard uses Server-Sent Events (SSE) for incremental updates.
- **Stale Detection**: Agents that haven't reported in 60 seconds (configurable) are automatically marked as `STALE` in the dashboard and API (unless in a terminal state).
- **Hybrid Interface**: Shared service layer ensures consistency across MCP, REST, and the Web UI.
- **Single-Instance Design**: The current MVP is designed for single-instance `stdio` transport. The service logic is shared but initialized independently for the MCP tool execution and the FastAPI web application to avoid fragile import-time global state.

## Limitations & Human Review

As an MVP, this system has several limitations:
- **No Authentication**: The API and dashboard have no built-in authentication. Do not expose this server to the public internet without a reverse proxy providing auth and TLS.
- **Single-Instance**: Designed for a single-process/single-instance deployment. Multiple instances sharing the same SQLite DB may work but SSE broadcasting and in-memory caches are not synchronized across processes.
- **Manual SSE Verification**: While the core service and REST API are covered by automated tests, the SSE streaming functionality currently requires manual verification or browser-based integration tests.
- **CLI Polling**: The CLI monitor uses fixed-interval polling without adaptive backoff.
- **AI-Generated Lifecycle**: The core application lifecycle and repository patterns were scaffolded with AI assistance and should be reviewed before use in security-critical or high-availability environments.

## Testing

Run tests with pytest:
```bash
pytest
```
