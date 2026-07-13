CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY, workspace_path TEXT, workspace_hash TEXT,
  task_description TEXT, state TEXT, termination_reason TEXT,
  step_count INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS steps (
  step_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, step_index INTEGER,
  action_json TEXT, governance_decision TEXT, triggered_rule_id TEXT,
  tool_result_json TEXT, feedback_category TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS approval_requests (
  approval_id TEXT PRIMARY KEY, task_id TEXT, step_index INTEGER,
  action_snapshot_json TEXT, action_fingerprint TEXT,
  governance_decision TEXT, triggered_rule_id TEXT, reason TEXT,
  risk_explanation TEXT, state TEXT, remember_choice INTEGER DEFAULT 0,
  created_at TEXT, decided_at TEXT, decided_by TEXT);
CREATE TABLE IF NOT EXISTS audit_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
  step_index INTEGER, timestamp TEXT, event_type TEXT,
  payload_json TEXT, prev_hash TEXT, hash TEXT);
CREATE TABLE IF NOT EXISTS memories (
  memory_id TEXT PRIMARY KEY, project_id TEXT, type TEXT, key TEXT,
  value TEXT, tags_json TEXT, source TEXT, confirmed INTEGER,
  created_at TEXT, last_used_at TEXT, use_count INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS task_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
  step_index INTEGER, file_path TEXT, snapshot_path TEXT, created_at TEXT);
