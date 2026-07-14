"""aegiscode/persistence/repositories.py -- thin CRUD repositories.

Parameterized SQL only. created_at/updated_at = ISO 8601 UTC.
All public methods return plain dicts or lists of dicts.
"""
from __future__ import annotations

import datetime
import json
import uuid


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class TaskRepository:
    """CRUD for the tasks table."""

    def __init__(self, conn):
        self._conn = conn

    def insert(self, workspace_path: str, workspace_hash: str, task_description: str) -> str:
        task_id = str(uuid.uuid4())
        now = _now_iso()
        self._conn.execute(
            "INSERT INTO tasks(task_id, workspace_path, workspace_hash, task_description,"
            " state, termination_reason, step_count, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (task_id, workspace_path, workspace_hash, task_description,
             "RUNNING", None, 0, now, now),
        )
        self._conn.commit()
        return task_id

    def get(self, task_id: str) -> dict:
        row = self._conn.execute(
            "SELECT task_id, workspace_path, workspace_hash, task_description,"
            " state, termination_reason, step_count, created_at, updated_at"
            " FROM tasks WHERE task_id=?",
            (task_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"task not found: {task_id}")
        keys = ("task_id", "workspace_path", "workspace_hash", "task_description",
                "state", "termination_reason", "step_count", "created_at", "updated_at")
        return dict(zip(keys, row))

    def update_state(self, task_id: str, state: str, termination_reason: str | None = None,
                     step_count: int | None = None) -> None:
        now = _now_iso()
        if step_count is not None:
            self._conn.execute(
                "UPDATE tasks SET state=?, termination_reason=?, step_count=?, updated_at=?"
                " WHERE task_id=?",
                (state, termination_reason, step_count, now, task_id),
            )
        else:
            self._conn.execute(
                "UPDATE tasks SET state=?, termination_reason=?, updated_at=?"
                " WHERE task_id=?",
                (state, termination_reason, now, task_id),
            )
        self._conn.commit()


class StepRepository:
    """CRUD for the steps table."""

    def __init__(self, conn):
        self._conn = conn

    def insert(
        self,
        task_id: str,
        step_index: int,
        action_json: str,
        governance_decision: str,
        triggered_rule_id: str | None,
        tool_result_json: str,
        feedback_category: str,
    ) -> None:
        now = _now_iso()
        self._conn.execute(
            "INSERT INTO steps(task_id, step_index, action_json, governance_decision,"
            " triggered_rule_id, tool_result_json, feedback_category, created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (task_id, step_index, action_json, governance_decision,
             triggered_rule_id, tool_result_json, feedback_category, now),
        )
        self._conn.commit()

    def list_for_task(self, task_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT step_id, task_id, step_index, action_json, governance_decision,"
            " triggered_rule_id, tool_result_json, feedback_category, created_at"
            " FROM steps WHERE task_id=? ORDER BY step_index",
            (task_id,),
        ).fetchall()
        keys = ("step_id", "task_id", "step_index", "action_json", "governance_decision",
                "triggered_rule_id", "tool_result_json", "feedback_category", "created_at")
        return [dict(zip(keys, row)) for row in rows]


class ApprovalRepository:
    """CRUD for the approval_requests table."""

    def __init__(self, conn):
        self._conn = conn

    def insert(
        self,
        task_id: str,
        step_index: int,
        action_snapshot: dict,
        action_fingerprint: str,
        governance_decision: str,
        triggered_rule_id: str | None,
        reason: str,
        risk_explanation: str,
    ) -> str:
        approval_id = str(uuid.uuid4())
        now = _now_iso()
        self._conn.execute(
            "INSERT INTO approval_requests("
            " approval_id, task_id, step_index, action_snapshot_json, action_fingerprint,"
            " governance_decision, triggered_rule_id, reason, risk_explanation,"
            " state, remember_choice, created_at, decided_at, decided_by)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                approval_id,
                task_id,
                step_index,
                json.dumps(action_snapshot, sort_keys=True),
                action_fingerprint,
                governance_decision,
                triggered_rule_id,
                reason,
                risk_explanation,
                "PENDING",
                0,
                now,
                None,
                None,
            ),
        )
        self._conn.commit()
        return approval_id

    def get(self, approval_id: str) -> dict:
        row = self._conn.execute(
            "SELECT approval_id, task_id, step_index, action_snapshot_json, action_fingerprint,"
            " governance_decision, triggered_rule_id, reason, risk_explanation,"
            " state, remember_choice, created_at, decided_at, decided_by"
            " FROM approval_requests WHERE approval_id=?",
            (approval_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"approval not found: {approval_id}")
        keys = ("approval_id", "task_id", "step_index", "action_snapshot_json",
                "action_fingerprint", "governance_decision", "triggered_rule_id",
                "reason", "risk_explanation", "state", "remember_choice",
                "created_at", "decided_at", "decided_by")
        return dict(zip(keys, row))

    def update_state(self, approval_id: str, state: str, decided_by: str = "service") -> None:
        now = _now_iso()
        self._conn.execute(
            "UPDATE approval_requests SET state=?, decided_at=?, decided_by=?"
            " WHERE approval_id=?",
            (state, now, decided_by, approval_id),
        )
        self._conn.commit()

    def list_for_task(self, task_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT approval_id, task_id, step_index, action_snapshot_json, action_fingerprint,"
            " governance_decision, triggered_rule_id, reason, risk_explanation,"
            " state, remember_choice, created_at, decided_at, decided_by"
            " FROM approval_requests WHERE task_id=? ORDER BY created_at",
            (task_id,),
        ).fetchall()
        keys = ("approval_id", "task_id", "step_index", "action_snapshot_json",
                "action_fingerprint", "governance_decision", "triggered_rule_id",
                "reason", "risk_explanation", "state", "remember_choice",
                "created_at", "decided_at", "decided_by")
        return [dict(zip(keys, row)) for row in rows]


class AuditEventRepository:
    """Read-only access to audit_events for service queries (written by AuditLog.append)."""

    def __init__(self, conn):
        self._conn = conn

    def list_since(self, task_id: str, since: int) -> list[dict]:
        """Return events for task_id with event_id > since."""
        rows = self._conn.execute(
            "SELECT event_id, task_id, step_index, timestamp, event_type, payload_json,"
            " prev_hash, hash FROM audit_events"
            " WHERE task_id=? AND event_id>? ORDER BY event_id",
            (task_id, since),
        ).fetchall()
        keys = ("event_id", "task_id", "step_index", "timestamp", "event_type",
                "payload_json", "prev_hash", "hash")
        return [dict(zip(keys, row)) for row in rows]
