PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_versions (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL,
  description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plugin_runs (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  hermes_version TEXT,
  plugin_version TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  profile_name TEXT,
  mode TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  platform TEXT,
  model TEXT,
  profile_name TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  meta_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS turns (
  turn_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  index_in_session INTEGER,
  status TEXT,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  monotonic_ns INTEGER,
  session_id TEXT,
  turn_id TEXT,
  task_id TEXT,
  tool_call_id TEXT,
  source TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  redaction_json TEXT NOT NULL DEFAULT '{}',
  correlation_quality TEXT NOT NULL DEFAULT 'unmatched',
  lossy INTEGER NOT NULL DEFAULT 0,
  plugin_version TEXT,
  hermes_version TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);

CREATE TABLE IF NOT EXISTS event_losses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  reason TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 1,
  details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS blobs (
  digest TEXT PRIMARY KEY,
  size_bytes INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  content_type TEXT,
  path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  created_at TEXT NOT NULL,
  digest TEXT,
  meta_json TEXT NOT NULL DEFAULT '{}',
  canonical_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  audit_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  actor TEXT NOT NULL,
  command TEXT NOT NULL,
  args_json TEXT NOT NULL,
  config_hash TEXT,
  result TEXT NOT NULL,
  side_effects_json TEXT NOT NULL DEFAULT '[]',
  approval_ref TEXT
);

CREATE TABLE IF NOT EXISTS dataset_manifests (
  manifest_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  name TEXT NOT NULL,
  split TEXT NOT NULL,
  locked INTEGER NOT NULL DEFAULT 0,
  manifest_hash TEXT NOT NULL,
  body_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
  candidate_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  candidate_hash TEXT NOT NULL UNIQUE,
  parent_hash TEXT,
  target_type TEXT NOT NULL,
  status TEXT NOT NULL,
  body_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_results (
  result_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  candidate_hash TEXT NOT NULL,
  dataset_hash TEXT,
  metrics_json TEXT NOT NULL,
  label TEXT,
  body_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS purity_registry_versions (
  registry_hash TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  version TEXT NOT NULL,
  body_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS correlations (
  correlation_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  left_id TEXT NOT NULL,
  right_id TEXT NOT NULL,
  quality TEXT NOT NULL,
  confidence REAL,
  explanation_json TEXT NOT NULL DEFAULT '{}'
);
