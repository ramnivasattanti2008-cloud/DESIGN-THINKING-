-- Session log (SQLite). Append-only. Not wired up yet: the API keeps sessions in memory.
-- Raw frames are never stored here (see docs/architecture/OVERVIEW.md).

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
  payload     TEXT NOT NULL DEFAULT '{}',  -- JSON, structured data only
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, id);
