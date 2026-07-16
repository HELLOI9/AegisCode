"""aegiscode/demo/service.py -- DemoRunManager.

Runs each shared demo scenario (aegiscode/demo/scenarios.py) through the REAL
HarnessCore + MockLLM + governance + approval state machine + audit chain, in
an isolated per-run temp workspace, with cleanup -- reusing the existing
ApplicationService (never reimplements the loop, never bypasses governance or
approval).

Security boundary (see .superpowers/sdd/DESIGN.md "安全边界"):
  * ``start_run`` accepts ONLY a whitelisted ``scenario_id`` -- no user-supplied
    workspace, script, command, tool list, or absolute path ever reaches this
    class from a caller.
  * Every run gets its own temp workspace under ``allowed_base`` and its own
    fresh ``MockLLM`` instance -- MockLLM cursors and writable workspaces are
    NEVER shared across runs.
  * ``get_run`` never surfaces raw tool arguments (file content, shell
    commands, absolute paths) -- only tool name / governance decision /
    feedback category, mirroring ApplicationService._project_steps' shape.
  * Cleanup removes only the per-run temp directory it created, is idempotent
    (safe to call again after the directory is already gone), and never
    touches anything outside ``allowed_base``.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from types import SimpleNamespace
from typing import Callable

from aegiscode.audit.chain import AuditLog
from aegiscode.config.schema import AegisConfig, Feedback, Limits, Tools, Workspace
from aegiscode.demo.scenarios import (
    DemoScenario,
    build_run_outcome,
    evaluate,
    get_scenario,
)
from aegiscode.governance.factory import build_dispatcher
from aegiscode.llm.mock import MockLLM
from aegiscode.loop.harness import HarnessCore
from aegiscode.service.app_service import ApplicationService
from aegiscode.service.assembly import _build_registry, _make_final_verifier
from aegiscode.persistence.db import open_db

# Terminal task states (see app_service._termination_to_state).
_TERMINAL_STATES = {"COMPLETED", "CANCELLED", "FAILED"}

# Duplicated verbatim from demos/demo2_feedback_loop.py::_CHECK_PY. Kept as a
# local copy rather than an import so aegiscode/ (library) never depends on
# demos/ (top-level CLI scripts) -- the dependency direction is the other way
# around (demos/*.py imports FROM aegiscode.demo.scenarios).
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


def _materialize_fixture(fixture: str | None, workspace: str) -> None:
    """Scaffold *fixture* into *workspace*. No fixture -> nothing."""
    if fixture is None:
        return
    if fixture == "calc":
        src_dir = os.path.join(workspace, "src")
        os.makedirs(src_dir, exist_ok=True)
        check_path = os.path.join(workspace, "check.py")
        with open(check_path, "w", encoding="utf-8") as fh:
            fh.write(_CHECK_PY)
        return
    raise ValueError(f"unknown demo fixture: {fixture!r}")


def _build_config(scenario: DemoScenario, workspace: str, allowed_base: str) -> AegisConfig:
    """Per-run AegisConfig scoped to *workspace*, gated to the scenario's tools."""
    import sys

    kwargs = {}
    if scenario.fixture == "calc":
        kwargs["feedback"] = Feedback(test_command=f"{sys.executable} check.py")
    return AegisConfig(
        workspace=Workspace(root=workspace, allowed_base=allowed_base),
        limits=Limits(
            max_steps=scenario.max_steps,
            max_consecutive_failures=scenario.max_consecutive_failures,
        ),
        tools=Tools(enabled=list(scenario.enabled_tools)),
        **kwargs,
    )


def _build_final_verifier(scenario: DemoScenario, config: AegisConfig, workspace: str):
    """demo2-style re-run of the check command for the 'calc' fixture; otherwise
    an always-true verifier (no fixture means no re-runnable check to verify).
    """
    if scenario.fixture == "calc":
        return _make_final_verifier(config, workspace)
    return lambda: True


def _wrap_supersede_resolver(base_resolver: Callable) -> Callable:
    """Demo③ seam: call #1 delegates to the real resolver; call #2 mutates the
    action's arguments AFTER the harness has already captured its approved
    fingerprint, then approves -- reproducing the SUPERSEDED invalidation path
    with a genuine (not theatrical) fingerprint mismatch inside HarnessCore.
    """
    call_count = {"n": 0}

    def resolver(action, verdict):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return base_resolver(action, verdict)
        action.arguments["content"] = "<mutated>"
        return True

    return resolver


def _normalize_event_type(event_type) -> str:
    """Normalize a raw audit row's event_type to its plain string value.

    ``aegiscode.audit.chain.AuditLog.append`` stores ``str(event_type)`` for
    whatever it's handed, and ``aegiscode.loop.harness`` always hands it the
    raw ``EventType`` enum member (never ``.value``). Because ``EventType``
    is a ``str``-mixin ``Enum``, ``Enum.__str__`` wins over ``str.__str__``,
    so the value actually persisted to sqlite is the qualified repr
    (``"EventType.ACTION_PROPOSED"``) rather than the plain value
    (``"ACTION_PROPOSED"``). ``build_run_outcome`` (aegiscode/demo/scenarios.py,
    out of scope for this task) does exact literal comparisons against the
    plain value, so real sqlite-backed rows must be normalized before being
    handed to it. Idempotent: already-plain values pass through unchanged.
    """
    text = str(event_type)
    prefix = "EventType."
    if text.startswith(prefix):
        return text[len(prefix):]
    return text


def _normalize_events(raw_events: list[dict]) -> list[dict]:
    """Return a shallow-copied list of *raw_events* with event_type normalized.

    See ``_normalize_event_type`` for why this is necessary. Non-dict rows
    are passed through unchanged (defensive; not expected in practice).
    """
    normalized = []
    for row in raw_events:
        if isinstance(row, dict) and "event_type" in row:
            row = dict(row)
            row["event_type"] = _normalize_event_type(row["event_type"])
        normalized.append(row)
    return normalized


def _summarize_steps(raw_events: list[dict]) -> list[dict]:
    """Build a redacted, human-readable per-step summary from raw audit rows.

    Groups by step_index and exposes ONLY tool name / governance decision /
    feedback category -- never action.arguments (which can carry file
    content, shell commands, or absolute paths).
    """
    import json

    step_map: dict[int, dict] = {}
    order: list[int] = []
    for row in raw_events:
        step_index = row.get("step_index")
        if step_index is None:
            continue
        event_type = row.get("event_type")
        try:
            payload = json.loads(row.get("payload_json") or "{}")
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}

        if step_index not in step_map:
            step_map[step_index] = {"step": step_index}
            order.append(step_index)
        entry = step_map[step_index]

        if event_type == "ACTION_PROPOSED":
            entry["tool"] = payload.get("tool")
        elif event_type == "GOVERNANCE_DECISION":
            entry["governance_decision"] = payload.get("decision")
        elif event_type == "APPROVAL_DECIDED":
            entry["approval_state"] = payload.get("state")
        elif event_type == "TOOL_EXECUTED":
            entry["tool_status"] = payload.get("status")
        elif event_type == "FEEDBACK":
            entry["feedback_category"] = payload.get("category")

    return [step_map[i] for i in sorted(order)]


class DemoRunManager:
    """Runs shared demo scenarios through the real harness stack.

    Builds ONE demo-aware ApplicationService(sync=...) internally, wired to a
    per-scenario harness_factory that reverse-looks-up which scenario a given
    workspace belongs to (never trusts caller-supplied wiring). Exposed as
    ``.service`` so a future HTTP API layer can reuse ``get_events`` /
    ``list_approvals`` / ``decide`` for the same run_id (== task_id).
    """

    def __init__(
        self,
        allowed_base: str,
        db_path: str,
        sync: bool = False,
        sync_decision_fn: Callable[[str], bool] | None = None,
    ):
        self._allowed_base = allowed_base
        os.makedirs(allowed_base, exist_ok=True)

        # workspace -> scenario_id: the harness_factory reverse-looks-up which
        # scenario a run belongs to. Never trust a caller-supplied scenario at
        # harness-build time -- only what start_run recorded itself.
        self._ws_to_scenario: dict[str, str] = {}
        # run_id (== task_id) -> {"scenario_id": ..., "workspace": ...}
        self._run_meta: dict[str, dict] = {}
        # Per-run demo3 seam state, keyed by workspace (set up in start_run,
        # consumed by harness_factory when building the approval_resolver).
        self._ws_llms: dict[str, MockLLM] = {}

        conn = open_db(db_path)
        self._conn = conn

        self.service = ApplicationService(
            db=conn,
            db_path=db_path,
            config=AegisConfig(workspace=Workspace(root=allowed_base, allowed_base=allowed_base)),
            harness_factory=self._harness_factory,
            sync=sync,
            sync_decision_fn=sync_decision_fn,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_run(self, scenario_id: str) -> str:
        """Start a real harness run of the whitelisted scenario *scenario_id*.

        Takes NO user-supplied workspace/script/command/path -- only the
        scenario id, which is validated against the shared registry
        (UnknownScenarioError, a KeyError subclass, if not found).
        """
        scenario = get_scenario(scenario_id)  # raises UnknownScenarioError

        self._sweep_orphaned_runs()

        workspace = tempfile.mkdtemp(prefix="aegis_demorun_", dir=self._allowed_base)
        _materialize_fixture(scenario.fixture, workspace)

        self._ws_to_scenario[workspace] = scenario_id
        self._ws_llms[workspace] = MockLLM(list(scenario.mock_script))

        run_id = self.service.create_task(workspace, description=scenario_id)
        self._run_meta[run_id] = {"scenario_id": scenario_id, "workspace": workspace}
        return run_id

    def get_run(self, run_id: str) -> dict:
        """Return {scenario_id, state, acceptance, steps, done} for *run_id*.

        Raises KeyError for an unknown run_id. When the task has reached a
        terminal state, the per-run temp workspace is cleaned up (idempotent).
        """
        meta = self._run_meta[run_id]  # raises KeyError for unknown run_id
        scenario_id = meta["scenario_id"]
        scenario = get_scenario(scenario_id)

        task = self.service.get_task(run_id)
        state = task["state"]
        done = state in _TERMINAL_STATES

        raw_events = _normalize_events(self.service.get_events(run_id, 0))
        outcome = build_run_outcome(scenario_id, state, raw_events)
        acceptance = evaluate(scenario, outcome)
        steps = _summarize_steps(raw_events)

        if done:
            self._cleanup_workspace(meta["workspace"])

        return {
            "scenario_id": scenario_id,
            "state": state,
            "acceptance": acceptance,
            "steps": steps,
            "done": done,
        }

    def list_scenarios(self):
        from aegiscode.demo.scenarios import list_scenarios

        return list_scenarios()

    # ------------------------------------------------------------------
    # Internal wiring
    # ------------------------------------------------------------------

    def _cleanup_workspace(self, workspace: str) -> None:
        """Idempotent: safe to call even if the directory is already gone."""
        if workspace and os.path.isdir(workspace):
            shutil.rmtree(workspace, ignore_errors=True)
        self._ws_to_scenario.pop(workspace, None)
        self._ws_llms.pop(workspace, None)

    def _sweep_orphaned_runs(self) -> None:
        """Reclaim terminal-state runs whose temp workspace still exists.

        Backstop for the ``get_run`` fast-path cleanup: in async mode a run
        completes in a background thread, and if the client never polls
        ``get_run`` again (closed tab, crash, abandoned run) the per-run
        ``aegis_demorun_*`` dir would otherwise accumulate under
        ``allowed_base`` forever. Called from ``start_run`` before creating a
        new run, this bounds accumulation to the still-running + not-yet-swept
        set.

        ``_run_meta`` is intentionally NOT evicted -- an idempotent
        ``get_run`` after cleanup must still return the settled result.
        Reading task state is guarded so a missing task row never raises.
        """
        for run_id, meta in list(self._run_meta.items()):
            workspace = meta.get("workspace")
            if not workspace or not os.path.isdir(workspace):
                continue
            try:
                state = self.service.get_task(run_id)["state"]
            except KeyError:
                continue
            if state in _TERMINAL_STATES:
                self._cleanup_workspace(workspace)

    def _fallback_harness(self, task_id, workspace, cancel_check, audit_conn):
        """Keyless harness for a workspace this manager never registered.

        Reached when create_task runs on a workspace that did NOT come through
        ``start_run`` (e.g. a manual POST /tasks in demo mode, whose ephemeral
        demo workspace this manager doesn't know). Using an empty ``MockLLM``
        makes the run terminate as LLM_ERROR on the first turn instead of
        raising ``KeyError`` here — which, on the async run thread, would leave
        the task stuck RUNNING. Demo runs never hit this path: ``start_run``
        always registers the workspace first.
        """
        config = AegisConfig(
            workspace=Workspace(root=workspace, allowed_base=self._allowed_base)
        )
        registry = _build_registry(config)
        dispatcher = build_dispatcher(config, registry)

        def resolve(p: str) -> str:
            return p if os.path.isabs(p) else os.path.join(workspace, p)

        ctx = SimpleNamespace(
            task_id=task_id,
            workspace_root=workspace,
            resolve=resolve,
            snapshot=lambda abspath: None,
            write_max_bytes=config.tools.write_max_bytes,
        )
        audit_log = AuditLog(audit_conn if audit_conn is not None else self._conn)
        return HarnessCore(
            llm=MockLLM([]),
            dispatcher=dispatcher,
            audit=audit_log,
            config=config,
            ctx=ctx,
            final_verifier=lambda: False,
            cancel_check=cancel_check,
        )

    def _harness_factory(
        self, task_id, workspace, approval_resolver=None, cancel_check=None, audit_conn=None
    ):
        scenario_id = self._ws_to_scenario.get(workspace)
        if scenario_id is None:
            return self._fallback_harness(task_id, workspace, cancel_check, audit_conn)
        scenario = get_scenario(scenario_id)

        config = _build_config(scenario, workspace, self._allowed_base)
        llm = self._ws_llms[workspace]
        registry = _build_registry(config)
        dispatcher = build_dispatcher(config, registry)

        def resolve(p: str) -> str:
            return p if os.path.isabs(p) else os.path.join(workspace, p)

        ctx = SimpleNamespace(
            task_id=task_id,
            workspace_root=workspace,
            resolve=resolve,
            snapshot=lambda abspath: None,
            write_max_bytes=config.tools.write_max_bytes,
        )
        audit_log = AuditLog(audit_conn if audit_conn is not None else self._conn)

        resolver = approval_resolver
        if scenario.interactive_approval and resolver is not None:
            resolver = _wrap_supersede_resolver(resolver)

        return HarnessCore(
            llm=llm,
            dispatcher=dispatcher,
            audit=audit_log,
            config=config,
            ctx=ctx,
            final_verifier=_build_final_verifier(scenario, config, workspace),
            approval_resolver=resolver,
            cancel_check=cancel_check,
        )

