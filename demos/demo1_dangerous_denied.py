"""SPEC §16.4 demo① — governance intercepts a dangerous command.

Mechanism: the command-rules / policy engine DENIES ``rm -rf /`` *before* the
tool runs. A spy ``run_command`` tool records every execution, so an assertion
that it executed zero times is meaningful: if governance were broken the spy
counter would be non-zero.

Wiring is real: a genuine ``Dispatcher`` built by ``build_dispatcher`` over a
real ``ToolRegistry``, driven by one ``MockLLM`` step whose raw text is parsed
by the real ``parse_action`` and dispatched through the real governance gate.
"""
from __future__ import annotations

import tempfile
from types import SimpleNamespace

from aegiscode.config.schema import AegisConfig
from aegiscode.governance.decision import Decision
from aegiscode.governance.factory import build_dispatcher
from aegiscode.llm.mock import MockLLM
from aegiscode.protocol.parser import parse_action
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.result import ToolResult


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
    """Drive one dangerous step through real governance.

    Returns ``{"executed": <spy count>, "decision": <verdict decision value>}``.
    Contract: ``{"executed": 0, "decision": "DENY"}``.
    """
    cfg = AegisConfig()
    registry = ToolRegistry()
    spy = _SpyCommandTool()
    registry.register(spy)
    dispatcher = build_dispatcher(cfg, registry)

    llm = MockLLM(['{"tool":"run_command","arguments":{"command":"rm -rf /"}}'])
    raw = llm.complete([{"role": "user", "content": "clean up the repo"}])
    action = parse_action(raw)

    with tempfile.TemporaryDirectory() as ws:
        ctx = SimpleNamespace(workspace_root=ws, resolve=lambda p: p)
        verdict, result = dispatcher.dispatch(action, ctx)

    # The spy must never have executed — this is what makes DENY meaningful.
    assert spy.executions == 0, "SECURITY FAILURE: dangerous command executed"
    assert verdict.decision == Decision.DENY

    return {"executed": spy.executions, "decision": verdict.decision.value}


if __name__ == "__main__":  # pragma: no cover
    r = run()
    print(
        "demo① dangerous-command DENY: "
        f"executed={r['executed']} decision={r['decision']} "
        "(governance intercepted `rm -rf /`, tool NOT executed)"
    )
