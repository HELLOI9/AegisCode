"""SPEC §16.4 demo③ — approval binding + invalidation lifecycle (live harness).

Mechanism (proven end-to-end through the REAL HarnessCore, no theater):

  1. The MockLLM proposes a HIGH-RISK ``write_file`` to ``docs/approved.txt`` — a
     path OUTSIDE the write allowlist (``src/``, ``tests/``), so the real
     governance ``default_fn`` returns REQUIRE_APPROVAL. The harness PAUSES: it
     captures ``approved_fp = fingerprint(action)`` and calls the
     ``approval_resolver`` BEFORE any tool runs. At that instant the spy tool's
     execution counter is still 0 (nothing has executed yet).

  2. The human APPROVES the original action unchanged. Because the about-to-run
     action still matches ``approved_fp``, ``execute_approved`` runs the real
     ``WriteFileTool`` — ``docs/approved.txt`` genuinely lands on disk and a
     ``TOOL_EXECUTED`` + ``APPROVAL_DECIDED state=APPROVED`` pair is audited.

  3. On a later turn the MockLLM proposes a DIFFERENT high-risk write
     (``docs/superseded.txt``). This also hits REQUIRE_APPROVAL, but the resolver
     MUTATES ``action.arguments`` AFTER the harness already captured the
     fingerprint (models plan-drift / async-resume divergence — the exact
     pattern from tests/loop/test_approval_binding.py). The mutated action no
     longer matches the approved fingerprint, so ``validate_resume`` raises
     ``SupersededError``: ``execute_approved`` returns a denied result flagged
     ``artifacts["superseded"]``. The harness audits ``APPROVAL_DECIDED
     state=SUPERSEDED``, feeds back POLICY_DENIED, and continues WITHOUT running
     the tool. The mutated file NEVER lands on disk.

Three independent, REAL proofs make the lifecycle meaningful:
  * A spy ``write_file`` tool counts executions AND records paths: it is 0 at the
    pause, 1 after approval, and never counts the superseded write.
  * On-disk state: ``docs/approved.txt`` exists; the superseded file does not.
  * The audit log — read back through the real ``AuditEventRepository`` — carries
    both ``APPROVAL_DECIDED APPROVED`` and ``APPROVAL_DECIDED SUPERSEDED``.

The run is fully deterministic: MockLLM only (zero network), a
``TemporaryDirectory`` workspace, and ``max_steps`` bounding so the loop stops
right after the finish step.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from aegiscode.audit.chain import AuditLog
from aegiscode.audit.events import EventType
from aegiscode.config.schema import AegisConfig, Limits, Workspace
from aegiscode.governance.approval import ApprovalStore, fingerprint
from aegiscode.governance.factory import build_dispatcher
from aegiscode.llm.mock import MockLLM
from aegiscode.loop.harness import HarnessCore
from aegiscode.persistence.db import open_db
from aegiscode.persistence.repositories import AuditEventRepository
from aegiscode.protocol.action import Action
from aegiscode.tools.file_tools import WriteFileTool
from aegiscode.tools.finish_tool import FinishTool
from aegiscode.tools.registry import ToolRegistry

_TASK_ID = "demo3"
_APPROVED_PATH = "docs/approved.txt"
_SUPERSEDED_PATH = "docs/superseded.txt"
_APPROVED_CONTENT = "approved-write\n"
_SUPERSEDED_CONTENT = "original-content-the-human-would-have-seen\n"
_MUTATED_CONTENT = "MUTATED-after-approval\n"

class _SpyWriteFileTool:
    """Wraps the REAL WriteFileTool, recording every execution.

    Delegating to the real tool means the on-disk proof is genuine (the approved
    write actually creates the file); the counter + path log let the demo prove
    the exact "count=0 at pause / count=1 after approval / superseded never
    counted" lifecycle.
    """

    name = "write_file"

    def __init__(self) -> None:
        self._inner = WriteFileTool()
        self.executions = 0
        self.written_paths: list[str] = []

    def run(self, arguments, ctx):
        self.executions += 1
        self.written_paths.append(arguments.get("path", ""))
        return self._inner.run(arguments, ctx)


class _LifecycleResolver:
    """Approval seam driving the full bind → approve → supersede lifecycle.

    Round 1 (docs/approved.txt): approve the action UNCHANGED. It matches the
      fingerprint the harness captured, so it executes.
    Round 2 (docs/superseded.txt): approve but MUTATE ``action.arguments`` after
      the harness already bound ``approved_fp``. The mutated action diverges from
      the approved fingerprint → SUPERSEDED → it must NOT run.

    The resolver also records the spy execution count AT THE MOMENT it is first
    called: the harness invokes the resolver before ``execute_approved``, so this
    captures the "paused before any execution" fact authentically. It builds a
    real ApprovalRequest via ApprovalStore.create so the demo can prove the
    normalized action snapshot + fingerprint were captured at request time.
    """

    def __init__(self, spy: _SpyWriteFileTool, store: ApprovalStore) -> None:
        self._spy = spy
        self._store = store
        self._call = 0
        self.exec_count_at_first_pause: int | None = None
        self.first_request = None  # the ApprovalRequest built at round-1 pause

    def __call__(self, action, verdict) -> bool:
        self._call += 1
        if self._call == 1:
            # Prove the pause happened before ANY tool executed.
            self.exec_count_at_first_pause = self._spy.executions
            # Persist a normalized approval request (snapshot + fingerprint +
            # risk info) exactly as a real approval store would at request time.
            self.first_request = self._store.create(
                task_id=_TASK_ID,
                step_index=0,
                snapshot={"tool": action.tool, "arguments": dict(action.arguments)},
                fp=fingerprint(action),
                rule_id=verdict.rule_id,
                reason=verdict.reason,
                risk="HIGH: write outside the allowlisted directories",
            )
            return True
        # Round 2: divergence introduced AFTER the harness captured the
        # approved fingerprint — the mutated action can't ride the old approval.
        action.arguments["content"] = _MUTATED_CONTENT
        return True


def run() -> dict:
    """Drive the full approval binding + invalidation lifecycle through the harness.

    Returns a contract dict whose keys each pin one lifecycle guarantee:
      * ``paused_for_approval``            — an approval was required with tool
        exec count 0 at the pause (nothing ran before the human decided).
      * ``approval_saved_normalized``      — the approval request captured the
        normalized action snapshot + a fingerprint that matches it.
      * ``original_executed_after_approval`` — the unchanged approved action ran
        exactly once and ``docs/approved.txt`` landed on disk.
      * ``modified_superseded``            — the mutated action was SUPERSEDED
        (audit event present).
      * ``modified_not_executed``          — the mutated action never ran: the
        spy count stayed at 1 and its file is absent from disk.
      * ``audit_has_approval_flow``        — the audit trail (read back through
        AuditEventRepository) records APPROVED then SUPERSEDED.
    """
    with tempfile.TemporaryDirectory() as ws_str:
        ws = Path(ws_str)

        config = AegisConfig(
            workspace=Workspace(root=str(ws)),
            # Two approval turns + one finish = 3 steps. max_steps=3 lets the
            # finish land, then turn 4 hits MAX_STEPS before the exhausted MockLLM
            # is called again — fully deterministic (no LLM_ERROR). A generous
            # failure budget keeps the SUPERSEDED turn (a POLICY_DENIED failure)
            # from tripping MAX_CONSECUTIVE_FAILURES before finish.
            limits=Limits(max_steps=3, max_consecutive_failures=5),
        )

        registry = ToolRegistry()
        spy = _SpyWriteFileTool()
        registry.register(spy)
        registry.register(FinishTool())
        dispatcher = build_dispatcher(config, registry)

        conn = open_db(str(ws / "audit.db"))
        audit = AuditLog(conn)

        def resolve(p: str) -> str:
            import os

            return p if os.path.isabs(p) else os.path.join(str(ws), p)

        ctx = SimpleNamespace(
            task_id=_TASK_ID,
            workspace_root=str(ws),
            resolve=resolve,
            snapshot=lambda abspath: None,
            write_max_bytes=config.tools.write_max_bytes,
        )

        store = ApprovalStore()
        resolver = _LifecycleResolver(spy, store)

        # Scripted turns: approve+execute original, then the mutated/superseded
        # write, then finish. The second write proposes ORIGINAL content — the
        # resolver mutates it after the fingerprint is bound, so supersession is
        # caused by the resolver seam, not by the LLM emitting different text.
        llm = MockLLM([
            json.dumps({"tool": "write_file",
                        "arguments": {"path": _APPROVED_PATH, "content": _APPROVED_CONTENT}}),
            json.dumps({"tool": "write_file",
                        "arguments": {"path": _SUPERSEDED_PATH, "content": _SUPERSEDED_CONTENT}}),
            json.dumps({"tool": "finish", "arguments": {}}),
        ])

        harness = HarnessCore(
            llm=llm,
            dispatcher=dispatcher,
            audit=audit,
            config=config,
            ctx=ctx,
            final_verifier=lambda: True,
            approval_resolver=resolver,
        )
        harness.run("write project notes")

        # On-disk truth: only the approved file should exist.
        approved_on_disk = (ws / _APPROVED_PATH).exists()
        superseded_on_disk = (ws / _SUPERSEDED_PATH).exists()

        # Read the audit trail back through the real repository (same path the
        # service layer uses) and inspect the actual stored rows.
        events = AuditEventRepository(conn).list_since(_TASK_ID, 0)

    approved_event = False
    superseded_event = False
    for ev in events:
        if ev["event_type"] != str(EventType.APPROVAL_DECIDED):
            continue
        payload = json.loads(ev["payload_json"])
        if payload.get("state") == "APPROVED":
            approved_event = True
        elif payload.get("state") == "SUPERSEDED":
            superseded_event = True

    # ---- prove each lifecycle guarantee ----
    paused_for_approval = resolver.exec_count_at_first_pause == 0

    req = resolver.first_request
    approval_saved_normalized = (
        req is not None
        and req.action_snapshot == {
            "tool": "write_file",
            "arguments": {"path": _APPROVED_PATH, "content": _APPROVED_CONTENT},
        }
        # The stored fingerprint must match the normalized snapshot it captured.
        and req.action_fingerprint == fingerprint(
            Action(tool=req.action_snapshot["tool"],
                   arguments=req.action_snapshot["arguments"])
        )
    )

    original_executed_after_approval = (
        spy.executions == 1
        and spy.written_paths == [_APPROVED_PATH]
        and approved_on_disk
    )
    modified_not_executed = (
        spy.executions == 1                      # count did NOT increase
        and _SUPERSEDED_PATH not in spy.written_paths
        and not superseded_on_disk               # nothing landed on disk
    )
    audit_has_approval_flow = approved_event and superseded_event

    # Loud, self-failing asserts (mirror demo1 style) so a broken mechanism
    # crashes the demo instead of silently returning False.
    assert paused_for_approval, "approval did not pause before any tool executed"
    assert approval_saved_normalized, "approval request did not capture normalized action + fp"
    assert original_executed_after_approval, "approved original action did not execute exactly once"
    assert superseded_event, "no APPROVAL_DECIDED SUPERSEDED recorded in audit log"
    assert modified_not_executed, "SECURITY FAILURE: superseded action executed"
    assert audit_has_approval_flow, "audit log missing the APPROVED→SUPERSEDED flow"

    return {
        "paused_for_approval": paused_for_approval,
        "approval_saved_normalized": approval_saved_normalized,
        "original_executed_after_approval": original_executed_after_approval,
        "modified_superseded": superseded_event,
        "modified_not_executed": modified_not_executed,
        "audit_has_approval_flow": audit_has_approval_flow,
    }


if __name__ == "__main__":  # pragma: no cover
    r = run()
    print(
        "demo③ approval binding + invalidation: "
        f"paused_for_approval={r['paused_for_approval']} "
        f"approval_saved_normalized={r['approval_saved_normalized']} "
        f"original_executed_after_approval={r['original_executed_after_approval']} "
        f"modified_superseded={r['modified_superseded']} "
        f"modified_not_executed={r['modified_not_executed']} "
        f"audit_has_approval_flow={r['audit_has_approval_flow']} "
        "(approved original ran; mutated action superseded, never executed)"
    )

