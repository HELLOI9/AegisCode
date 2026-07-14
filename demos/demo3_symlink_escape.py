"""SPEC §16.4 demo③ — path fence denies a symlink escape.

Mechanism: the path fence resolves a path to its realpath and denies anything
that escapes the workspace root. Here a real in-workspace symlink
``evil -> /etc/passwd`` is created; a ``read_file`` on it must be DENIED and no
file content may leak back through the tool result.

Wiring is real: a genuine ``Dispatcher`` built by ``build_dispatcher`` over a
real ``ToolRegistry`` containing the real ``ReadFileTool``. If the fence were
broken the tool would run and ``/etc/passwd`` bytes would appear in the result.
"""
from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace

from aegiscode.config.schema import AegisConfig
from aegiscode.governance.decision import Decision
from aegiscode.governance.factory import build_dispatcher
from aegiscode.llm.mock import MockLLM
from aegiscode.protocol.parser import parse_action
from aegiscode.tools.file_tools import ReadFileTool
from aegiscode.tools.registry import ToolRegistry


def run() -> dict:
    """Attempt to read a symlink that escapes the workspace.

    Returns ``{"decision": <verdict decision value>, "leaked": <bool>}``.
    Contract: ``decision == "DENY"`` (and ``leaked is False``).
    """
    cfg = AegisConfig()
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    dispatcher = build_dispatcher(cfg, registry)

    llm = MockLLM(['{"tool":"read_file","arguments":{"path":"evil"}}'])
    raw = llm.complete([{"role": "user", "content": "read the evil file"}])
    action = parse_action(raw)

    with tempfile.TemporaryDirectory() as ws:
        link = os.path.join(ws, "evil")
        os.symlink("/etc/passwd", link)

        def resolve(p: str) -> str:
            return p if os.path.isabs(p) else os.path.join(ws, p)

        ctx = SimpleNamespace(workspace_root=ws, resolve=resolve)
        verdict, result = dispatcher.dispatch(action, ctx)

        # Sanity: the symlink genuinely points at a real out-of-workspace file,
        # so a broken fence really would leak. Guard against a vacuous demo.
        assert os.path.realpath(link) == "/etc/passwd"

    detail = result.detail_for_llm if result is not None else ""
    leaked = "root:" in detail or "/bin/" in detail
    assert verdict.decision == Decision.DENY
    assert not leaked, "SECURITY FAILURE: sensitive file content leaked"

    return {"decision": verdict.decision.value, "leaked": leaked}


if __name__ == "__main__":  # pragma: no cover
    r = run()
    print(
        "demo③ symlink-escape DENY: "
        f"decision={r['decision']} leaked={r['leaked']} "
        "(path fence blocked `evil -> /etc/passwd`, no content leaked)"
    )
