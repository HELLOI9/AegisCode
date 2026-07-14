"""SPEC §16.4 demo③ — path fence denies a symlink escape.

Mechanism (proven end-to-end through the REAL harness, no theater):
  1. A real in-workspace symlink ``evil -> /etc/passwd`` is created.
  2. One ``MockLLM`` step scripts a ``read_file`` on ``evil``.
  3. A genuine ``Dispatcher`` (``build_dispatcher``) over the real ``ReadFileTool``
     runs the path fence: it resolves ``evil`` to its realpath, sees it escapes
     the workspace root, and DENIES *before* the tool reads anything.
  4. The real ``HarnessCore`` drives that step against a real ``AuditLog`` on a
     tmp sqlite db. On a DENY it emits a ``GOVERNANCE_DECISION`` (decision=DENY,
     carrying the fence's rule_id) and does NOT emit ``TOOL_EXECUTED`` — so no
     ``/etc/passwd`` bytes are ever read.

Anti-vacuous guard: the demo asserts the symlink genuinely resolves to
``/etc/passwd`` (a real out-of-workspace file), so a broken fence really would
leak. It also asserts no sensitive content leaked into any audit payload.

``max_steps=1`` bounds the run to that single step: turn 2 terminates with
MAX_STEPS *before* the (exhausted) MockLLM is called again, so the demo is fully
deterministic (no LLM_ERROR).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from aegiscode.audit.chain import AuditLog
from aegiscode.audit.events import EventType
from aegiscode.config.schema import AegisConfig, Limits, Workspace
from aegiscode.governance.factory import build_dispatcher
from aegiscode.llm.mock import MockLLM
from aegiscode.loop.harness import HarnessCore
from aegiscode.persistence.db import open_db
from aegiscode.persistence.repositories import AuditEventRepository
from aegiscode.tools.file_tools import ReadFileTool
from aegiscode.tools.registry import ToolRegistry

_TASK_ID = "demo3"


def run() -> dict:
    """Attempt to read a symlink that escapes the workspace, through the harness.

    Returns a dict with the existing contract keys ``decision`` and ``leaked``
    plus SPEC §16.4 audit proof: ``audit_has_deny`` (a GOVERNANCE_DECISION with
    decision DENY was recorded) and ``no_tool_executed`` (no TOOL_EXECUTED event
    — the read never ran).
    """
    with tempfile.TemporaryDirectory() as ws_str:
        ws = Path(ws_str)
        link = os.path.join(str(ws), "evil")
        os.symlink("/etc/passwd", link)

        # Sanity: the symlink genuinely points at a real out-of-workspace file,
        # so a broken fence really would leak. Guard against a vacuous demo.
        assert os.path.realpath(link) == "/etc/passwd"

        config = AegisConfig(
            workspace=Workspace(root=str(ws)),
            # Bound the loop to exactly one step (see module docstring).
            limits=Limits(max_steps=1),
        )

        registry = ToolRegistry()
        registry.register(ReadFileTool())
        dispatcher = build_dispatcher(config, registry)

        conn = open_db(str(ws / "audit.db"))
        audit = AuditLog(conn)

        def resolve(p: str) -> str:
            return p if os.path.isabs(p) else os.path.join(str(ws), p)

        ctx = SimpleNamespace(
            task_id=_TASK_ID,
            workspace_root=str(ws),
            resolve=resolve,
            snapshot=lambda abspath: None,
            write_max_bytes=config.tools.write_max_bytes,
        )

        llm = MockLLM(
            [json.dumps({"tool": "read_file", "arguments": {"path": "evil"}})]
        )

        harness = HarnessCore(
            llm=llm,
            dispatcher=dispatcher,
            audit=audit,
            config=config,
            ctx=ctx,
            final_verifier=lambda: False,
        )
        harness.run("read the evil file")

        # Read the audit trail back through the real repository.
        events = AuditEventRepository(conn).list_since(_TASK_ID, 0)

    gov_deny = None
    tool_executed = False
    leaked = False
    for ev in events:
        payload = json.loads(ev["payload_json"])
        if ev["event_type"] == str(EventType.GOVERNANCE_DECISION) and payload.get("decision") == "DENY":
            gov_deny = payload
        if ev["event_type"] == str(EventType.TOOL_EXECUTED):
            tool_executed = True
        # No sensitive /etc/passwd content may appear in ANY audit payload.
        if "root:" in ev["payload_json"] or "/bin/" in ev["payload_json"]:
            leaked = True

    audit_has_deny = gov_deny is not None
    no_tool_executed = not tool_executed

    assert audit_has_deny, "no GOVERNANCE_DECISION DENY recorded in audit log"
    assert (gov_deny or {}).get("rule"), "DENY GOVERNANCE_DECISION did not carry a rule_id"
    assert no_tool_executed, "SECURITY FAILURE: TOOL_EXECUTED emitted — the read ran"
    assert not leaked, "SECURITY FAILURE: sensitive file content leaked"

    return {
        "decision": "DENY" if audit_has_deny else None,
        "leaked": leaked,
        "audit_has_deny": audit_has_deny,
        "no_tool_executed": no_tool_executed,
    }


if __name__ == "__main__":  # pragma: no cover
    r = run()
    print(
        "demo③ symlink-escape DENY: "
        f"decision={r['decision']} leaked={r['leaked']} "
        f"audit_has_deny={r['audit_has_deny']} no_tool_executed={r['no_tool_executed']} "
        "(path fence blocked `evil -> /etc/passwd`, no content leaked, read NOT executed)"
    )
