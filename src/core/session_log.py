"""SessionLog: Append-only SQLite audit log for MIRROR session events.

Uses the schema defined in db/schema.sql. Parameterized queries only.
Raw frame image bytes (data_b64) are strictly rejected to guarantee privacy and storage bounds.
"""
import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_FILE = Path(__file__).resolve().parent.parent.parent / "db" / "schema.sql"

DEFAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id          TEXT PRIMARY KEY,
  goal        TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT NOT NULL REFERENCES sessions(id),
  kind        TEXT NOT NULL CHECK (kind IN ('observe', 'plan', 'verify', 'user_override')),
  step_id     TEXT,
  tier        TEXT CHECK (tier IN ('A0', 'A1', 'A2', 'A3')),
  rule_id     TEXT,
  decision    TEXT CHECK (decision IN ('allow', 'confirm', 'block')),
  status      TEXT CHECK (status IN ('verified', 'not_verified', 'cannot_tell')),
  payload     TEXT NOT NULL DEFAULT '{}',
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, id);
"""


def _has_data_b64(item: Any) -> bool:
    """Recursively checks if any dictionary key is 'data_b64'."""
    if isinstance(item, dict):
        if "data_b64" in item:
            return True
        return any(_has_data_b64(v) for v in item.values())
    if isinstance(item, list):
        return any(_has_data_b64(elem) for elem in item)
    return False


class SessionLog:
    """Append-only SQLite session audit log."""

    def __init__(self, path: str = ":memory:"):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema from db/schema.sql or embedded fallback."""
        if SCHEMA_FILE.exists():
            schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
        else:
            schema_sql = DEFAULT_SCHEMA
        self.conn.executescript(schema_sql)
        self.conn.commit()

    def start_session(self, session_id: str, goal: str) -> None:
        """Records a new mission session."""
        if not session_id or not session_id.strip():
            raise ValueError("session_id cannot be empty")
        if not goal or not goal.strip():
            raise ValueError("goal cannot be empty")
        with self.conn:
            self.conn.execute(
                "INSERT INTO sessions (id, goal) VALUES (?, ?)",
                (session_id.strip(), goal.strip()),
            )

    def add_event(
        self,
        session_id: str,
        kind: str,
        *,
        step_id: str | None = None,
        tier: str | None = None,
        rule_id: str | None = None,
        decision: str | None = None,
        status: str | None = None,
        payload: dict[str, Any] | str | None = None,
    ) -> int:
        """Appends a structured event to the session audit log."""
        if payload is not None:
            if isinstance(payload, dict):
                if _has_data_b64(payload):
                    raise ValueError("payload contains forbidden image data key 'data_b64'")
                payload_json = json.dumps(payload)
            elif isinstance(payload, str):
                try:
                    parsed = json.loads(payload)
                    if _has_data_b64(parsed):
                        raise ValueError("payload contains forbidden image data key 'data_b64'")
                except json.JSONDecodeError:
                    if "data_b64" in payload:
                        raise ValueError("payload contains forbidden image data key 'data_b64'")
                payload_json = payload
            else:
                raise TypeError(f"payload must be dict, json string, or None, got {type(payload)}")
        else:
            payload_json = "{}"

        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO events (
                    session_id, kind, step_id, tier, rule_id, decision, status, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, kind, step_id, tier, rule_id, decision, status, payload_json),
            )
            return cursor.lastrowid

    def events(self, session_id: str) -> list[dict[str, Any]]:
        """Returns all events recorded for a session, strictly ordered by ID ascending."""
        cursor = self.conn.execute(
            """
            SELECT id, session_id, kind, step_id, tier, rule_id, decision, status, payload, created_at
            FROM events
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        )
        out = []
        for row in cursor.fetchall():
            out.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "kind": row["kind"],
                    "step_id": row["step_id"],
                    "tier": row["tier"],
                    "rule_id": row["rule_id"],
                    "decision": row["decision"],
                    "status": row["status"],
                    "payload": row["payload"],
                    "created_at": row["created_at"],
                }
            )
        return out

    def close(self) -> None:
        """Closes the underlying database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
