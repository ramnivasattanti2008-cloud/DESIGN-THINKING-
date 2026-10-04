"""The port the session engine writes audit events to.

The engine depends only on this Protocol, so the SQLite writer (src/core/session_log.py) and any
test double can be plugged in without the engine knowing which one it has.

Only labels and structured fields cross this boundary. Frames and `data_b64` content never do
(db/schema.sql: raw frames are never stored). Allowed values follow the CHECK constraints in
db/schema.sql: kind observe | plan | verify | user_override, tier A0-A3, decision allow | confirm |
block, status verified | not_verified | cannot_tell.
"""
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SessionLogSink(Protocol):
    # The engine ignores return values, so they are left open (a writer may return a row id).

    def start_session(self, session_id: str, goal: str) -> object: ...

    def add_event(self, session_id: str, kind: str, *, step_id: str | None = None,
                  tier: str | None = None, rule_id: str | None = None,
                  decision: str | None = None, status: str | None = None,
                  payload: dict[str, Any] | None = None) -> object: ...
