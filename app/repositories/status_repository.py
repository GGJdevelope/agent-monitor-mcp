import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime, timezone
from app.models.status import StatusEvent, AgentStatus, AgentState

logger = logging.getLogger(__name__)


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
            # Check if we need to migrate
            cursor = conn.execute("PRAGMA table_info(agent_current_status)")
            columns = [row["name"] for row in cursor.fetchall()]

            if columns and "instance_id" not in columns:
                logger.info("Migrating database to instance-aware schema")
                self._migrate_to_instance_aware(conn)

            # Events table (append-only)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_status_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instance_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    message TEXT,
                    reported_at TEXT NOT NULL,
                    metadata TEXT,
                    branch TEXT,
                    working_dir TEXT
                )
            """)

            # Current snapshot table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_current_status (
                    instance_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    message TEXT,
                    reported_at TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT,
                    branch TEXT,
                    working_dir TEXT
                )
            """)

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_instance_run ON agent_status_events (instance_id, run_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_reported_at ON agent_status_events (reported_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_current_updated_at ON agent_current_status (updated_at)"
            )
            conn.commit()

    def _migrate_to_instance_aware(self, conn: sqlite3.Connection):
        """Migrate legacy schema to instance-aware schema."""
        # 1. Rename old tables
        conn.execute("ALTER TABLE agent_status_events RENAME TO legacy_events")
        conn.execute("ALTER TABLE agent_current_status RENAME TO legacy_snapshots")

        # 2. Create new tables
        conn.execute("""
            CREATE TABLE agent_status_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL,
                message TEXT,
                reported_at TEXT NOT NULL,
                metadata TEXT,
                branch TEXT,
                working_dir TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE agent_current_status (
                instance_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL,
                message TEXT,
                reported_at TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT,
                branch TEXT,
                working_dir TEXT
            )
        """)

        # 3. Backfill snapshots (instance_id = agent_id:run_id for legacy)
        conn.execute("""
            INSERT INTO agent_current_status (
                instance_id, agent_id, run_id, task_name, status, progress, message, 
                reported_at, first_seen_at, updated_at, metadata
            )
            SELECT 
                agent_id || ':' || run_id, agent_id, run_id, task_name, status, progress, message, 
                reported_at, first_seen_at, updated_at, metadata
            FROM legacy_snapshots
        """)

        # 4. Backfill events
        conn.execute("""
            INSERT INTO agent_status_events (
                instance_id, agent_id, run_id, task_name, status, progress, message, 
                reported_at, metadata
            )
            SELECT 
                agent_id || ':' || run_id, agent_id, run_id, task_name, status, progress, message, 
                reported_at, metadata
            FROM legacy_events
        """)

        # 5. Drop legacy tables
        conn.execute("DROP TABLE legacy_events")
        conn.execute("DROP TABLE legacy_snapshots")

    def prune_expired_data(self, cutoff: datetime) -> dict[str, int]:
        """
        Prune rows strictly older than the cutoff datetime.
        - Events are pruned by 'reported_at'
        - Snapshots are pruned by 'updated_at' (as per plan)
        Returns a dictionary with 'deleted_events' and 'deleted_snapshots' counts.
        """
        cutoff_iso = cutoff.isoformat()

        logger.info(f"Pruning agent data older than {cutoff_iso}")

        try:
            with self._get_connection() as conn:
                # Use a single transaction for atomicity
                with conn:
                    # Prune events older than cutoff
                    cursor = conn.execute(
                        "DELETE FROM agent_status_events WHERE reported_at < ?",
                        (cutoff_iso,),
                    )
                    deleted_events = cursor.rowcount

                    # Prune current status snapshots older than cutoff
                    cursor = conn.execute(
                        "DELETE FROM agent_current_status WHERE updated_at < ?",
                        (cutoff_iso,),
                    )
                    deleted_snapshots = cursor.rowcount

            logger.info(
                f"Pruned {deleted_events} events and {deleted_snapshots} snapshots"
            )
            return {
                "deleted_events": deleted_events,
                "deleted_snapshots": deleted_snapshots,
            }
        except sqlite3.Error as e:
            logger.error(f"Failed to prune expired agent data: {e}")
            raise

    def add_event(self, event: StatusEvent):
        # Ensure instance_id is present (defensive fallback)
        instance_id = event.instance_id or f"{event.agent_id}:{event.run_id}"

        with self._get_connection() as conn:
            # 1. Insert into events history
            conn.execute(
                """
                INSERT INTO agent_status_events (instance_id, agent_id, run_id, task_name, status, progress, message, reported_at, metadata, branch, working_dir)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    instance_id,
                    event.agent_id,
                    event.run_id,
                    event.task_name,
                    event.status.value,
                    event.progress,
                    event.message,
                    event.reported_at.isoformat(),
                    json.dumps(event.metadata),
                    event.branch,
                    event.working_dir,
                ),
            )

            # 2. Update current snapshot
            now = datetime.now(timezone.utc).isoformat()

            # Try to get existing record to preserve first_seen_at
            cursor = conn.execute(
                "SELECT first_seen_at FROM agent_current_status WHERE instance_id = ?",
                (instance_id,),
            )
            row = cursor.fetchone()
            first_seen_at = (
                row["first_seen_at"] if row else event.reported_at.isoformat()
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO agent_current_status 
                (instance_id, agent_id, run_id, task_name, status, progress, message, reported_at, first_seen_at, updated_at, metadata, branch, working_dir)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    instance_id,
                    event.agent_id,
                    event.run_id,
                    event.task_name,
                    event.status.value,
                    event.progress,
                    event.message,
                    event.reported_at.isoformat(),
                    first_seen_at,
                    now,
                    json.dumps(event.metadata),
                    event.branch,
                    event.working_dir,
                ),
            )
            conn.commit()

    def get_all_snapshots(self) -> List[AgentState]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agent_current_status")
            rows = cursor.fetchall()
            return [self._row_to_state(row) for row in rows]

    def get_snapshot(self, instance_id: str) -> Optional[AgentState]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM agent_current_status WHERE instance_id = ?",
                (instance_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_state(row)

    def get_events(self, instance_id: str, limit: int = 100) -> List[StatusEvent]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM agent_status_events WHERE instance_id = ? ORDER BY reported_at DESC LIMIT ?",
                (instance_id, limit),
            )
            rows = cursor.fetchall()
            return [
                StatusEvent(
                    instance_id=row["instance_id"],
                    agent_id=row["agent_id"],
                    run_id=row["run_id"],
                    task_name=row["task_name"],
                    status=AgentStatus(row["status"]),
                    progress=row["progress"],
                    message=row["message"],
                    reported_at=datetime.fromisoformat(row["reported_at"]),
                    metadata=json.loads(row["metadata"] or "{}"),
                    branch=row["branch"] if "branch" in list(row.keys()) else None,
                    working_dir=row["working_dir"]
                    if "working_dir" in list(row.keys())
                    else None,
                )
                for row in rows
            ]

    def _row_to_state(self, row: sqlite3.Row) -> AgentState:
        return AgentState(
            instance_id=row["instance_id"],
            agent_id=row["agent_id"],
            run_id=row["run_id"],
            task_name=row["task_name"],
            status=AgentStatus(row["status"]),
            progress=row["progress"],
            message=row["message"],
            reported_at=datetime.fromisoformat(row["reported_at"]),
            first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            metadata=json.loads(row["metadata"] or "{}"),
            branch=row["branch"] if "branch" in list(row.keys()) else None,
            working_dir=row["working_dir"]
            if "working_dir" in list(row.keys())
            else None,
        )
