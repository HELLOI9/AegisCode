"""SPEC §16.4 demo① — governance intercepts a dangerous command.

Mechanism (proven end-to-end through the REAL harness, no theater):
  1. One ``MockLLM`` step scripts a ``run_command`` for ``rm -rf /``.
  2. A genuine ``Dispatcher`` (``build_dispatcher``) runs the real governance
     gate. ``rm -rf /`` is refused DENY *before* execution — the ``/`` argument
     escapes the workspace so the run_command path fence (rule ``CMD_PATH_FENCE``)
     fires; ``rm`` is also absent from the command allowlist. Either way the tool
     never runs. (The demo asserts a DENY carrying a rule_id, not a specific
     rule, so it is robust to which gate fires first.)
  3. The real ``HarnessCore`` drives that step against a real ``AuditLog`` on a
     tmp sqlite db. On a DENY the harness genuinely emits a ``GOVERNANCE_DECISION``
     audit event (decision=DENY, carrying the rule_id) and a ``FEEDBACK`` event
     with category ``POLICY_DENIED`` — and it does NOT emit ``TOOL_EXECUTED``.

Two independent proofs make DENY meaningful:
  * A spy ``run_command`` tool records executions; it must stay at zero (if the
    gate were broken the counter would be non-zero).
  * The audit log — read back through the real ``AuditEventRepository`` — must
    contain the DENY ``GOVERNANCE_DECISION`` with a rule_id and the
    ``POLICY_DENIED`` feedback the agent receives (SPEC §16.4).

``max_steps=1`` bounds the run to that single step: turn 2 terminates with
MAX_STEPS *before* the (exhausted) MockLLM is called again, so the demo is fully
deterministic (no LLM_ERROR).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from aegiscode.audit.chain import AuditLog
from aegiscode.audit.events import EventType
from aegiscode.config.schema import AegisConfig, Limits, Workspace
from aegiscode.demo.scenarios import get_scenario
from aegiscode.governance.factory import build_dispatcher
from aegiscode.llm.mock import MockLLM
from aegiscode.loop.harness import HarnessCore
from aegiscode.persistence.db import open_db
from aegiscode.persistence.repositories import AuditEventRepository
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.result import ToolResult

_TASK_ID = "demo1"

# The MockLLM script fed into the harness — sourced from the shared scenario
# registry (single source of truth shared with the WebUI consumer) so the CLI
# and Web demos can never silently diverge.
_SCRIPT = list(get_scenario("dangerous-action-denial").mock_script)


class _SpyCommandTool:
    """Stand-in for the real run_command tool that records executions.

    It must NEVER be invoked in this demo: governance denies the action, so the
    dispatcher returns before calling ``run``.
    """

    name = "run_command"

    def __init__(self) -> None:
        self.executions = 0

    def run(self, arguments, ctx):  # pragma: no cover - proving it never runs
        self.executions += 1
        return ToolResult(tool=self.name, status="success", summary="ran command")


def run() -> dict:
    """Drive one dangerous step through the real harness + real governance.

    Returns a dict with the existing contract keys ``executed`` and ``decision``
    plus SPEC §16.4 audit proof: ``audit_has_deny`` (a GOVERNANCE_DECISION with
    decision DENY was recorded), ``deny_rule_id`` (the rule that denied it), and
    ``feedback_is_policy_denied`` (the agent received POLICY_DENIED feedback).
    """
    with tempfile.TemporaryDirectory() as ws_str:
        ws = Path(ws_str)
        config = AegisConfig(
            workspace=Workspace(root=str(ws)),
            # Bound the loop to exactly one step: after the DENY, turn 2 hits
            # MAX_STEPS before the exhausted MockLLM is called again (no LLM_ERROR).
            limits=Limits(max_steps=1),
        )

        registry = ToolRegistry()
        spy = _SpyCommandTool()
        registry.register(spy)
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

        llm = MockLLM(_SCRIPT)

        harness = HarnessCore(
            llm=llm,
            dispatcher=dispatcher,
            audit=audit,
            config=config,
            ctx=ctx,
            # Never reached (no finish action); DENY-only run.
            final_verifier=lambda: False,
        )
        harness.run("clean up the repo")

        # Read the audit trail back through the real repository (same path the
        # service layer uses) and inspect the actual stored rows.
        events = AuditEventRepository(conn).list_since(_TASK_ID, 0)

    gov_deny = None
    tool_executed = False
    feedback_is_policy_denied = False
    for ev in events:
        payload = json.loads(ev["payload_json"])
        if ev["event_type"] == str(EventType.GOVERNANCE_DECISION) and payload.get("decision") == "DENY":
            gov_deny = payload
        if ev["event_type"] == str(EventType.TOOL_EXECUTED):
            tool_executed = True
        if ev["event_type"] == str(EventType.FEEDBACK) and payload.get("category") == "POLICY_DENIED":
            feedback_is_policy_denied = True

    audit_has_deny = gov_deny is not None
    deny_rule_id = gov_deny.get("rule") if gov_deny else None

    # The spy must never have executed — this is what makes DENY meaningful.
    assert spy.executions == 0, "SECURITY FAILURE: dangerous command executed"
    # And the harness must not have logged a phantom execution.
    assert not tool_executed, "SECURITY FAILURE: TOOL_EXECUTED emitted on a DENY"
    assert audit_has_deny, "no GOVERNANCE_DECISION DENY recorded in audit log"
    assert deny_rule_id, "DENY GOVERNANCE_DECISION did not carry a rule_id"
    assert feedback_is_policy_denied, "agent did not receive POLICY_DENIED feedback"

    return {
        "executed": spy.executions,
        "decision": "DENY" if audit_has_deny else None,
        "audit_has_deny": audit_has_deny,
        "deny_rule_id": deny_rule_id,
        "feedback_is_policy_denied": feedback_is_policy_denied,
    }


if __name__ == "__main__":  # pragma: no cover
    r = run()
    print(
        "demo① dangerous-command DENY: "
        f"executed={r['executed']} decision={r['decision']} "
        f"audit_has_deny={r['audit_has_deny']} deny_rule_id={r['deny_rule_id']} "
        f"feedback_is_policy_denied={r['feedback_is_policy_denied']} "
        "(governance intercepted `rm -rf /`, tool NOT executed)"
    )
