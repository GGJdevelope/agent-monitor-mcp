import sqlite3
import json
from typing import List, Optional
from datetime import datetime, timezone
from app.models.status import StatusEvent, AgentStatus, AgentState

class StatusRepository:
    def __init__(self, db_path: str):
        # Handle sqlite:/// URI prefix if present
        if db_path.startswith("sqlite:///"):
            self.db_path = db_path[10:]
        else:
            self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            # Events table (append-only)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_status_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    message TEXT,
                    reported_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            # Current snapshot table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_current_status (
                    agent_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    message TEXT,
                    reported_at TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_agent_run ON agent_status_events (agent_id, run_id)")
            conn.commit()

    def add_event(self, event: StatusEvent):
        with self._get_connection() as conn:
            # 1. Insert into events history
            conn.execute(
                """
                INSERT INTO agent_status_events (agent_id, run_id, task_name, status, progress, message, reported_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.agent_id,
                    event.run_id,
                    event.task_name,
                    event.status.value,
                    event.progress,
                    event.message,
                    event.reported_at.isoformat(),
                    json.dumps(event.metadata)
                )
            )
            
            # 2. Update current snapshot
            now = datetime.now(timezone.utc).isoformat()
            
            # Try to get existing record to preserve first_seen_at
            cursor = conn.execute("SELECT first_seen_at FROM agent_current_status WHERE agent_id = ?", (event.agent_id,))
            row = cursor.fetchone()
            first_seen_at = row["first_seen_at"] if row else event.reported_at.isoformat()

            conn.execute(
                """
                INSERT OR REPLACE INTO agent_current_status 
                (agent_id, run_id, task_name, status, progress, message, reported_at, first_seen_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.agent_id,
                    event.run_id,
                    event.task_name,
                    event.status.value,
                    event.progress,
                    event.message,
                    event.reported_at.isoformat(),
                    first_seen_at,
                    now,
                    json.dumps(event.metadata)
                )
            )
            conn.commit()

    def get_all_snapshots(self) -> List[AgentState]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agent_current_status")
            rows = cursor.fetchall()
            return [self._row_to_state(row) for row in rows]

    def get_snapshot(self, agent_id: str) -> Optional[AgentState]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agent_current_status WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_state(row)

    def get_events(self, agent_id: str, limit: int = 100) -> List[StatusEvent]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM agent_status_events WHERE agent_id = ? ORDER BY reported_at DESC LIMIT ?",
                (agent_id, limit)
            )
            rows = cursor.fetchall()
            return [
                StatusEvent(
                    agent_id=row["agent_id"],
                    run_id=row["run_id"],
                    task_name=row["task_name"],
                    status=AgentStatus(row["status"]),
                    progress=row["progress"],
                    message=row["message"],
                    reported_at=datetime.fromisoformat(row["reported_at"]),
                    metadata=json.loads(row["metadata"] or "{}")
                )
                for row in rows
            ]

    def _row_to_state(self, row: sqlite3.Row) -> AgentState:
        return AgentState(
            agent_id=row["agent_id"],
            run_id=row["run_id"],
            task_name=row["task_name"],
            status=AgentStatus(row["status"]),
            progress=row["progress"],
            message=row["message"],
            reported_at=datetime.fromisoformat(row["reported_at"]),
            first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            metadata=json.loads(row["metadata"] or "{}")
        )
