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
import os
import threading
import uuid
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


class WorkspaceNotAllowedError(ValueError):
    """Raised when a requested workspace is outside the configured allowed base.

    A ValueError subclass so any generic ``except ValueError`` still catches it,
    while the API layer can map this specific type to HTTP 400 (bad request) —
    the request is well-formed but the workspace is not permitted.
    """


def _validate_workspace(workspace: str, allowed_base: str) -> None:
    """Fail closed unless *workspace* is the allowed base or a subdir of it.

    Symlink-safe: both sides are resolved with os.path.realpath, so a symlink
    inside the base that points outside (or a traversal) resolves to its real
    target before the containment check.

    Prefix-collision-safe: containment is decided by os.path.commonpath (path
    segments), NOT string prefix — so base '/x/ws' does NOT accept '/x/ws-evil'.
    """
    if not workspace or not isinstance(workspace, str):
        raise WorkspaceNotAllowedError("workspace must be a non-empty string")

    base_real = os.path.realpath(allowed_base)
    ws_real = os.path.realpath(workspace)
    try:
        # commonpath raises ValueError for mixed absolute/relative or different
        # drives; either way the workspace is not safely inside the base.
        if os.path.commonpath([ws_real, base_real]) != base_real:
            raise WorkspaceNotAllowedError(
                f"workspace {workspace!r} is outside the allowed base"
            )
    except ValueError as exc:
        raise WorkspaceNotAllowedError(
            f"workspace {workspace!r} is outside the allowed base"
        ) from exc


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
        Called as harness_factory(task_id, workspace, approval_resolver,
        cancel_check, audit_conn) and must return a HarnessCore. audit_conn is
        the connection the harness must build its AuditLog on (the execution
        thread's connection), so sqlite is never used cross-thread.
    sync : bool
        If True, run inline; if False, run in background thread.
    sync_decision_fn : Callable[[str], bool] | None
        Sync-mode only: given an approval_id, returns True to approve. When
        None, sync-mode approvals default to reject (False). This replaces the
        old test-only ``approval_decisions`` dict on the constructor; make_service
        injects a closure over any pre-seeded decisions.
    """

    # Default bound wait for an async approval decision (seconds). A never-decided
    # approval is treated as NOT approved after this, so a harness thread cannot
    # hang forever. Read from config.limits.approval_timeout_sec if present.
    _DEFAULT_APPROVAL_TIMEOUT_SEC = 3600.0

    def __init__(
        self,
        db,
        db_path: str,
        config,
        harness_factory: Callable,
        sync: bool = False,
        sync_decision_fn: Callable[[str], bool] | None = None,
    ):
        self._db = db
        self._db_path = db_path
        self._config = config
        self._harness_factory = harness_factory
        self._sync = sync
        self._sync_decision_fn = sync_decision_fn

        self._task_repo = TaskRepository(db)
        self._step_repo = StepRepository(db)
        self._approval_repo = ApprovalRepository(db)
        self._event_repo = AuditEventRepository(db)

        # task_id -> threading.Event (set = cancel requested)
        self._cancel_flags: dict[str, threading.Event] = {}
        # approval_id -> threading.Event (set = decision made)
        self._approval_events: dict[str, threading.Event] = {}
        # Guards all reads/writes of _approval_events so decide() can never miss
        # an Event that a resolver is about to (or has just) registered.
        self._approvals_lock = threading.Lock()

    def _approval_timeout_sec(self) -> float:
        return float(
            getattr(self._config.limits, "approval_timeout_sec", None)
            or self._DEFAULT_APPROVAL_TIMEOUT_SEC
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _allowed_base(self) -> str:
        """The server-side allowed workspace base.

        Policy: config.workspace.allowed_base if set, else config.workspace.root.
        Validated in create_task so BOTH the API and any other caller of
        create_task are protected — the check cannot be bypassed at the boundary.
        """
        ws = self._config.workspace
        return ws.allowed_base or ws.root

    def create_task(self, workspace: str, description: str, pre_cancel: bool = False) -> str:
        """Create a task and run it (sync inline or async background thread).

        The requested workspace is validated against the server-side allowed base
        FIRST — before any task row is inserted — so a rejected request creates no
        task and touches no host path (acceptance §八).
        """
        _validate_workspace(workspace, self._allowed_base())

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
        """Approve or reject a pending approval and unblock any waiting harness thread.

        The DB state update and the Event lookup happen under _approvals_lock so
        this can never race with a resolver that is mid-registration. Event.set()
        is safe even if the resolver has not yet reached wait() -- a later wait()
        returns immediately.
        """
        state = "APPROVED" if approved else "REJECTED"
        with self._approvals_lock:
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
        """Sync-mode resolver: consults the injected sync_decision_fn (no blocking)."""
        decide_fn = self._sync_decision_fn

        def resolver(action, verdict):
            fp = fingerprint(action)
            step_index = self._event_repo.latest_action_step_index(task_id)
            approval_id = self._approval_repo.insert(
                task_id=task_id,
                step_index=step_index,
                action_snapshot={"tool": action.tool, "arguments": action.arguments},
                action_fingerprint=fp,
                governance_decision=verdict.decision.value,
                triggered_rule_id=verdict.rule_id,
                reason=verdict.reason,
                risk_explanation=verdict.reason,
            )
            approved = bool(decide_fn(approval_id)) if decide_fn is not None else False
            state = "APPROVED" if approved else "REJECTED"
            self._approval_repo.update_state(approval_id, state)
            return approved

        return resolver

    def _build_async_approval_resolver(
        self,
        task_id: str,
        approval_repo: ApprovalRepository,
        event_repo: AuditEventRepository,
    ):
        """Async-mode resolver: blocks on a threading.Event until decide() is called.

        Ordering matters to avoid a lost wakeup: we mint the approval_id and
        register its Event UNDER _approvals_lock BEFORE inserting the PENDING row.
        That way decide() -- which takes the same lock -- can never look up the id
        and miss the Event. Event.set() before wait() is safe (wait returns at once).
        The wait is bounded; on timeout the approval is treated as NOT approved and
        the row is moved to a terminal REJECTED state so it never stays PENDING.
        """

        def resolver(action, verdict):
            fp = fingerprint(action)
            step_index = event_repo.latest_action_step_index(task_id)
            approval_id = str(uuid.uuid4())
            ev = threading.Event()
            # Register the Event, then persist the row, all under the lock so a
            # concurrent decide() either sees no id yet (row not inserted, so its
            # update_state is a harmless no-op and the resolver will re-read below)
            # or sees the Event we just registered.
            with self._approvals_lock:
                self._approval_events[approval_id] = ev
                approval_repo.insert(
                    task_id=task_id,
                    step_index=step_index,
                    action_snapshot={"tool": action.tool, "arguments": action.arguments},
                    action_fingerprint=fp,
                    governance_decision=verdict.decision.value,
                    triggered_rule_id=verdict.rule_id,
                    reason=verdict.reason,
                    risk_explanation=verdict.reason,
                    approval_id=approval_id,
                )

            decided = ev.wait(timeout=self._approval_timeout_sec())
            if not decided:
                # Never decided within the bound: fail closed and move the row to a
                # terminal state so it isn't stuck PENDING.
                approval_repo.update_state(approval_id, "REJECTED", decided_by="timeout")
                with self._approvals_lock:
                    self._approval_events.pop(approval_id, None)
                return False

            with self._approvals_lock:
                self._approval_events.pop(approval_id, None)
            # Re-read the authoritative state from the DB (a decision may have
            # arrived via any path) and respect it.
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

        # Sync mode runs on the calling thread, so the harness audit may safely
        # wrap the main connection.
        harness = self._harness_factory(
            task_id=task_id,
            workspace=workspace,
            approval_resolver=approval_resolver,
            cancel_check=cancel_check,
            audit_conn=self._db,
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
            thread_event_repo = AuditEventRepository(thread_conn)

            cancel_event = self._cancel_flags[task_id]
            cancel_check = cancel_event.is_set

            approval_resolver = self._build_async_approval_resolver(
                task_id, thread_approval_repo, thread_event_repo
            )

            # Cross-thread sqlite is unsafe: the harness must build its AuditLog on
            # THIS thread's connection, not the main-thread connection.
            harness = self._harness_factory(
                task_id=task_id,
                workspace=workspace,
                approval_resolver=approval_resolver,
                cancel_check=cancel_check,
                audit_conn=thread_conn,
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
