"""SPEC §16.4 demo② — failure feedback drives an action change → COMPLETED.

Mechanism (the golden path, proven end-to-end, no theater):
  1. The agent writes ``src/calc.py`` with a WRONG ``add`` (``return a - b``).
  2. ``run_tests`` runs a REAL subprocess (``python check.py``) that reads +
     exec's the just-written file and asserts ``add(1, 2) == 3`` — it genuinely
     FAILS.
  3. The harness classifies the failure as TEST_FAILURE and feeds it back into
     the round-3 LLM context.
  4. The agent writes a DIFFERENT, correct ``add`` (``return a + b``).
  5. ``run_tests`` runs the same real subprocess again — it now PASSES.
  6. The agent calls ``finish``; the ``final_verifier`` RE-RUNS the real check
     command and returns green, so COMPLETED is proven by the verifier, NOT by
     the LLM claiming success.

Why a ``python check.py`` subprocess and not ``pytest``: pytest is a dev-only
dependency and is NOT installed in the shipped runtime container, so a nested
``pytest`` would break ``aegiscode demo`` in Docker. A stdlib ``python`` check
is a genuine re-execution of the written code (fails-then-passes for real) and
runs anywhere Python does. The failure/pass signal comes from the subprocess
exit code, never from the MockLLM. The check reads + exec's the source bytes
(no ``import``) so there is no ``.pyc`` cache to make the demo flaky.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from aegiscode.audit.chain import AuditLog
from aegiscode.config.schema import AegisConfig, Feedback, Limits, Workspace
from aegiscode.demo.scenarios import get_scenario
from aegiscode.governance.factory import build_dispatcher
from aegiscode.llm.mock import MockLLM
from aegiscode.loop.harness import HarnessCore
from aegiscode.loop.termination import TerminationReason
from aegiscode.persistence.db import open_db
from aegiscode.tools.finish_tool import FinishTool
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.run_tests_tool import RunTestsTool
from aegiscode.tools.file_tools import WriteFileTool

# Wrong and correct implementations the agent writes in round 1 and round 3.
# Kept as constants for fixture-scaffolding + on-disk asserts below; the
# MockLLM script itself is sourced from the shared scenario registry
# (single source of truth shared with the WebUI consumer), and the assertion
# right after _SCRIPT proves these constants can't silently diverge from it.
_WRONG_IMPL = "def add(a, b):\n    return a - b\n"
_RIGHT_IMPL = "def add(a, b):\n    return a + b\n"

# A stdlib-only check that reads the written source and asserts add(1,2)==3.
# It deliberately reads+exec's the file bytes on every run instead of using
# `import`, so there is NO .pyc bytecode cache: two writes in the same
# filesystem mtime tick can't make a later run reuse stale wrong-impl bytecode.
# That keeps the demo fully deterministic (SPEC §A.4C). Exits non-zero on
# failure (feeds TEST_FAILURE), zero on pass.
_CHECK_PY = (
    "import os\n"
    "src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'calc.py')\n"
    "ns = {}\n"
    "with open(src, encoding='utf-8') as fh:\n"
    "    exec(compile(fh.read(), src, 'exec'), ns)\n"
    "got = ns['add'](1, 2)\n"
    "assert got == 3, f'add(1,2)={got} expected 3'\n"
    "print('ok')\n"
)

# The MockLLM script fed into the harness — sourced from the shared scenario
# registry so the CLI and Web demos can never silently diverge. Asserted
# against the _WRONG_IMPL/_RIGHT_IMPL constants above so those constants
# (kept for fixture-scaffolding + the on-disk proof) cannot drift from what
# the registry actually encodes.
_SCRIPT = list(get_scenario("feedback-driven-repair").mock_script)
assert _SCRIPT == [
    json.dumps({"tool": "write_file", "arguments": {"path": "src/calc.py", "content": _WRONG_IMPL}}),
    json.dumps({"tool": "run_tests", "arguments": {}}),
    json.dumps({"tool": "write_file", "arguments": {"path": "src/calc.py", "content": _RIGHT_IMPL}}),
    json.dumps({"tool": "run_tests", "arguments": {}}),
    json.dumps({"tool": "finish", "arguments": {}}),
], "scenario registry mock_script diverged from demo2's wrong/right impl constants"


class _RecordingLLM:
    """Wraps MockLLM to capture, per round (1-indexed), both the messages passed
    in and the raw action text returned.

    The messages let the demo prove the round-3 context actually carried the
    round-2 TEST_FAILURE feedback. The returned outputs let the demo derive
    ``action_changed`` from what genuinely flowed through the harness rather than
    from module constants.
    """

    def __init__(self, mock: MockLLM):
        self._mock = mock
        self.messages_by_round: dict[int, list[dict]] = {}
        self.output_by_round: dict[int, str] = {}
        self._round = 0

    def complete(self, messages):
        self._round += 1
        self.messages_by_round[self._round] = [dict(m) for m in messages]
        out = self._mock.complete(messages)
        self.output_by_round[self._round] = out
        return out


def run() -> dict:
    """Drive the real HarnessCore through fail→fix→pass→finish.

    Returns a dict with at least ``completed`` and ``action_changed``; also
    ``test_failure_seen_in_round3_context`` to honor the SPEC feedback
    assertion.
    """
    with tempfile.TemporaryDirectory() as ws_str:
        ws = Path(ws_str)
        # Real workspace scaffold: the check script lives at the root and imports
        # the agent-written src/calc.py. Only src/ is written by the agent (it is
        # in the default write allowlist), so governance stays honest.
        (ws / "src").mkdir()
        (ws / "check.py").write_text(_CHECK_PY, encoding="utf-8")

        config = AegisConfig(
            workspace=Workspace(root=str(ws)),
            limits=Limits(max_steps=20),
            feedback=Feedback(test_command=f"{sys.executable} check.py"),
        )

        # Real tools: real WriteFileTool + real RunTestsTool (subprocess) + finish.
        registry = ToolRegistry()
        registry.register(WriteFileTool())
        registry.register(
            RunTestsTool(
                test_command=config.feedback.test_command,
                timeout_sec=config.limits.command_timeout_sec,
                output_max_bytes=config.limits.output_max_bytes,
            )
        )
        registry.register(FinishTool())

        dispatcher = build_dispatcher(config, registry)

        conn = open_db(str(ws / "audit.db"))
        audit = AuditLog(conn)

        def resolve(p: str) -> str:
            import os

            return p if os.path.isabs(p) else os.path.join(str(ws), p)

        ctx = SimpleNamespace(
            task_id="demo2",
            workspace_root=str(ws),
            resolve=resolve,
            snapshot=lambda abspath: None,
            write_max_bytes=config.tools.write_max_bytes,
        )

        # final_verifier RE-RUNS the real check command in the workspace. COMPLETED
        # is granted only if the actual code passes — the LLM cannot fake it.
        def final_verifier() -> bool:
            import shlex

            p = subprocess.run(
                shlex.split(config.feedback.test_command),
                cwd=str(ws),
                capture_output=True,
                text=True,
                timeout=config.limits.command_timeout_sec,
            )
            return p.returncode == 0

        # Scripted golden path: write-wrong, test(fail), write-right, test(pass),
        # finish — sourced from the shared scenario registry via _SCRIPT.
        rec = _RecordingLLM(MockLLM(_SCRIPT))

        harness = HarnessCore(
            llm=rec,
            dispatcher=dispatcher,
            audit=audit,
            config=config,
            ctx=ctx,
            final_verifier=final_verifier,
        )

        reason = harness.run("Implement add(a, b) so the tests pass.")

        completed = reason == TerminationReason.COMPLETED

        # Derive action_changed from what ACTUALLY flowed through the harness:
        # the raw write_file action the LLM emitted in round 1 vs round 3. This
        # is real evidence the agent changed course after the failure, not a
        # comparison of two module constants.
        emitted_round1 = rec.output_by_round.get(1, "")
        emitted_round3 = rec.output_by_round.get(3, "")
        action_changed = (
            bool(emitted_round1)
            and bool(emitted_round3)
            and emitted_round1 != emitted_round3
        )

        # Did the round-3 LLM context actually carry the round-2 TEST_FAILURE?
        round3_msgs = rec.messages_by_round.get(3, [])
        round3_text = "\n".join(m.get("content", "") for m in round3_msgs)
        test_failure_seen = "TEST_FAILURE" in round3_text

        # On-disk proof the corrective write landed: the file the agent left
        # behind must contain the correct implementation, not the wrong one.
        final_src = (ws / "src" / "calc.py").read_text(encoding="utf-8")
        fix_on_disk = final_src == _RIGHT_IMPL

    assert completed, f"harness did not complete (reason={reason})"
    assert action_changed, "round-3 action did not differ from round-1"
    assert test_failure_seen, "round-3 context did not contain TEST_FAILURE feedback"
    assert fix_on_disk, "final src/calc.py is not the corrected implementation"

    return {
        "completed": completed,
        "action_changed": action_changed,
        "test_failure_seen_in_round3_context": test_failure_seen,
        "fix_on_disk": fix_on_disk,
    }


if __name__ == "__main__":  # pragma: no cover
    r = run()
    print(
        "demo② feedback loop: "
        f"completed={r['completed']} action_changed={r['action_changed']} "
        f"test_failure_seen_in_round3_context={r['test_failure_seen_in_round3_context']} "
        "(wrong impl → real test fail → fix → real test pass → verified finish)"
    )
