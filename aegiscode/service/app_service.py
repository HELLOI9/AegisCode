"""aegiscode/service/app_service.py -- ApplicationService.

Orchestrates HarnessCore runs with SQLite persistence.

Design decisions:
- sync=True  : harness.run() is called inline (blocking, deterministic for tests).
- sync=False : harness.run() in a background threading.Thread that opens its OWN
               sqlite connection (never shares the main conn across threads).
- Approval pause/resume (async mode):
    * approval_resolver inserts an approval_requests row, registers a threading.Event,
      then blocks on Event.wait().
    * ApplicationService.decide() updates the row and sets the Event.
- Approval (sync mode):
    * Uses a pre-seeded decisions dict (key "*" = default); no blocking needed.
- Step persistence:
    * After run completes, audit_events for the task are projected into steps rows.
      HarnessCore remains unmodified; the audit log is the system of record.
- TerminationReason -> state:
    * COMPLETED -> "COMPLETED", CANCELLED -> "CANCELLED", all others -> "FAILED"
"""
from __future__ import annotations

import hashlib
import json
import threading
from typing import Callable

from aegiscode.audit.chain import AuditLog
from aegiscode.audit.events import EventType
from aegiscode.governance.approval import fingerprint
from aegiscode.loop.termination import TerminationReason
from aegiscode.persistence.repositories import (
    ApprovalRepository,
    AuditEventRepository,
    StepRepository,
    TaskRepository,
)


def _workspace_hash(workspace: str) -> str:
    return hashlib.sha256(workspace.encode()).hexdigest()[:16]


def _termination_to_state(reason: TerminationReason) -> str:
    if reason == TerminationReason.COMPLETED:
        return "COMPLETED"
    if reason == TerminationReason.CANCELLED:
        return "CANCELLED"
    return "FAILED"


class ApplicationService:
    """Service layer over HarnessCore.

    Parameters
    ----------
    db : sqlite3.Connection
        The main (caller-thread) connection. Background threads open their own.
    db_path : str
        Filesystem path to the sqlite file (so background threads can open it).
    config : AegisConfig
    harness_factory : Callable
        Called as harness_factory(task_id, workspace, approval_resolver, cancel_check)
        and must return a HarnessCore.
    sync : bool
        If True, run inline; if False, run in background thread.
    approval_decisions : dict | None
        For sync mode tests: maps approval_id (or "*") -> bool.
    """

    def __init__(
        self,
        db,
        db_path: str,
        config,
        harness_factory: Callable,
        sync: bool = False,
        approval_decisions: dict | None = None,
    ):
        self._db = db
        self._db_path = db_path
        self._config = config
        self._harness_factory = harness_factory
        self._sync = sync
        self._approval_decisions: dict = approval_decisions or {}

        self._task_repo = TaskRepository(db)
        self._step_repo = StepRepository(db)
        self._approval_repo = ApprovalRepository(db)
        self._event_repo = AuditEventRepository(db)

        # task_id -> threading.Event (set = cancel requested)
        self._cancel_flags: dict[str, threading.Event] = {}
        # approval_id -> threading.Event (set = decision made)
        self._approval_events: dict[str, threading.Event] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_task(self, workspace: str, description: str, pre_cancel: bool = False) -> str:
        """Create a task and run it (sync inline or async background thread)."""
        task_id = self._task_repo.insert(workspace, _workspace_hash(workspace), description)

        cancel_event = threading.Event()
        self._cancel_flags[task_id] = cancel_event

        if pre_cancel:
            cancel_event.set()

        if self._sync:
            self._run_inline(task_id, workspace, description, cancel_event)
        else:
            t = threading.Thread(
                target=self._run_in_thread,
                args=(task_id, workspace, description),
                daemon=True,
            )
            t.start()

        return task_id

    def get_task(self, task_id: str) -> dict:
        """Return the task row as a dict. Raises KeyError if not found."""
        return self._task_repo.get(task_id)

    def get_events(self, task_id: str, since: int) -> list[dict]:
        """Return audit_events for task_id with event_id > since."""
        return self._event_repo.list_since(task_id, since)

    def list_approvals(self, task_id: str) -> list[dict]:
        """Return all approval_requests rows for the task."""
        return self._approval_repo.list_for_task(task_id)

    def decide(self, approval_id: str, approved: bool) -> None:
        """Approve or reject a pending approval and unblock any waiting harness thread."""
        state = "APPROVED" if approved else "REJECTED"
        self._approval_repo.update_state(approval_id, state)
        ev = self._approval_events.get(approval_id)
        if ev is not None:
            ev.set()

    def cancel(self, task_id: str) -> None:
        """Request cooperative cancellation of a running task."""
        ev = self._cancel_flags.get(task_id)
        if ev is not None:
            ev.set()

    def get_audit(self, task_id: str) -> dict:
        """Return audit events + chain validity for the task."""
        audit = AuditLog(self._db)
        chain_valid, _ = audit.verify_chain(task_id)
        events = self._event_repo.list_since(task_id, 0)
        return {"chain_valid": chain_valid, "events": events}

    # ------------------------------------------------------------------
    # Approval resolvers
    # ------------------------------------------------------------------

    def _build_sync_approval_resolver(self, task_id: str):
        """Sync-mode resolver: consults pre-seeded decisions dict."""
        decisions = self._approval_decisions

        def resolver(action, verdict):
            fp = fingerprint(action)
            approval_id = self._approval_repo.insert(
                task_id=task_id,
                step_index=0,
                action_snapshot={"tool": action.tool, "arguments": action.arguments},
                action_fingerprint=fp,
                governance_decision=verdict.decision.value,
                triggered_rule_id=verdict.rule_id,
                reason=verdict.reason,
                risk_explanation=verdict.reason,
            )
            # Look up per-id, then wildcard, then default False (reject)
            approved = decisions.get(approval_id, decisions.get("*", False))
            state = "APPROVED" if approved else "REJECTED"
            self._approval_repo.update_state(approval_id, state)
            return approved

        return resolver

    def _build_async_approval_resolver(self, task_id: str, approval_repo: ApprovalRepository):
        """Async-mode resolver: blocks on threading.Event until decide() is called."""

        def resolver(action, verdict):
            fp = fingerprint(action)
            approval_id = approval_repo.insert(
                task_id=task_id,
                step_index=0,
                action_snapshot={"tool": action.tool, "arguments": action.arguments},
                action_fingerprint=fp,
                governance_decision=verdict.decision.value,
                triggered_rule_id=verdict.rule_id,
                reason=verdict.reason,
                risk_explanation=verdict.reason,
            )
            ev = threading.Event()
            self._approval_events[approval_id] = ev
            ev.wait()  # Block until decide() sets this event
            row = approval_repo.get(approval_id)
            return row["state"] == "APPROVED"

        return resolver

    # ------------------------------------------------------------------
    # Runners
    # ------------------------------------------------------------------

    def _run_inline(
        self,
        task_id: str,
        workspace: str,
        description: str,
        cancel_event: threading.Event,
    ) -> None:
        """Run harness synchronously on the calling thread."""
        approval_resolver = self._build_sync_approval_resolver(task_id)
        cancel_check = cancel_event.is_set

        harness = self._harness_factory(
            task_id=task_id,
            workspace=workspace,
            approval_resolver=approval_resolver,
            cancel_check=cancel_check,
        )

        try:
            reason = harness.run(description)
        except Exception:
            reason = TerminationReason.INTERNAL_ERROR

        state = _termination_to_state(reason)
        step_count = self._project_steps(task_id, self._db)
        self._task_repo.update_state(task_id, state, reason.value, step_count)

    def _run_in_thread(self, task_id: str, workspace: str, description: str) -> None:
        """Run harness in a background thread with its own DB connection."""
        from aegiscode.persistence.db import open_db

        thread_conn = open_db(self._db_path)
        try:
            thread_task_repo = TaskRepository(thread_conn)
            thread_approval_repo = ApprovalRepository(thread_conn)

            cancel_event = self._cancel_flags[task_id]
            cancel_check = cancel_event.is_set

            approval_resolver = self._build_async_approval_resolver(
                task_id, thread_approval_repo
            )

            harness = self._harness_factory(
                task_id=task_id,
                workspace=workspace,
                approval_resolver=approval_resolver,
                cancel_check=cancel_check,
            )

            try:
                reason = harness.run(description)
            except Exception:
                reason = TerminationReason.INTERNAL_ERROR

            state = _termination_to_state(reason)
            step_count = self._project_steps(task_id, thread_conn)
            thread_task_repo.update_state(task_id, state, reason.value, step_count)
        finally:
            thread_conn.close()

    # ------------------------------------------------------------------
    # Step projection
    # ------------------------------------------------------------------

    def _project_steps(self, task_id: str, conn) -> int:
        """Project audit_events into steps rows and return step count.

        We read the audit log (system of record) and build a steps row for each
        agent step. This keeps HarnessCore pure while giving us a queryable table.
        """
        step_repo = StepRepository(conn)

        rows = conn.execute(
            "SELECT step_index, event_type, payload_json FROM audit_events"
            " WHERE task_id=? ORDER BY event_id",
            (task_id,),
        ).fetchall()

        # Accumulate per-step: {step_index: {action, governance, feedback}}
        step_map: dict[int, dict] = {}
        for step_index, event_type, payload_json in rows:
            try:
                payload = json.loads(payload_json)
            except (json.JSONDecodeError, TypeError):
                payload = {}

            si = step_index
            if event_type == EventType.ACTION_PROPOSED.value:
                step_map.setdefault(si, {})["action"] = payload
            elif event_type == EventType.GOVERNANCE_DECISION.value:
                step_map.setdefault(si, {})["governance"] = payload
            elif event_type == EventType.FEEDBACK.value:
                step_map.setdefault(si, {})["feedback"] = payload

        step_count = 0
        for si in sorted(step_map):
            entry = step_map[si]
            action = entry.get("action", {})
            gov = entry.get("governance", {})
            feedback = entry.get("feedback", {})
            step_repo.insert(
                task_id=task_id,
                step_index=si,
                action_json=json.dumps(action, sort_keys=True),
                governance_decision=gov.get("decision", ""),
                triggered_rule_id=gov.get("rule"),
                tool_result_json="{}",
                feedback_category=feedback.get("category", ""),
            )
            step_count += 1

        return step_count
