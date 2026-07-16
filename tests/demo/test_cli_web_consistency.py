"""tests/demo/test_cli_web_consistency.py — CLI (make demo) ↔ Web (DemoRunManager)
must not diverge.

The single source of truth is aegiscode/demo/scenarios.py: both the CLI demos
(demos/*.py, driven by `make demo` via demos.run_demos) and the Web demo runner
(aegiscode.demo.service.DemoRunManager) must use the SAME demo ids, the SAME
MockLLM scripts, and the SAME success conditions. These tests fail loudly if a
future change lets one path drift from the other (e.g. a WebUI demo that renders
success while `make demo` would judge it a failure).
"""
from __future__ import annotations

from demos.run_demos import _DEMO_BY_NAME
from demos import (
    demo1_dangerous_denied,
    demo2_feedback_loop,
    demo3_approval_binding,
)
from aegiscode.demo.scenarios import REGISTRY, get_scenario, list_scenarios


# The CLI's stable --only selectors map 1:1 to the shared registry ids.
_CLI_NAME_TO_SCENARIO_ID = {
    "guardrail": "dangerous-action-denial",
    "feedback": "feedback-driven-repair",
    "approval": "approval-binding-invalidation",
}

# The CLI demo module that backs each scenario id (its _SCRIPT is what make demo
# actually feeds MockLLM).
_SCENARIO_ID_TO_CLI_MODULE = {
    "dangerous-action-denial": demo1_dangerous_denied,
    "feedback-driven-repair": demo2_feedback_loop,
    "approval-binding-invalidation": demo3_approval_binding,
}


def test_cli_selectors_map_onto_registry_ids():
    """Every CLI --only selector corresponds to a registry scenario id, and the
    map covers exactly the three shared scenarios (no orphan on either side)."""
    assert set(_DEMO_BY_NAME) == set(_CLI_NAME_TO_SCENARIO_ID)
    assert set(_CLI_NAME_TO_SCENARIO_ID.values()) == set(REGISTRY)
    assert len(list_scenarios()) == 3


def test_cli_and_web_use_the_same_mock_scripts():
    """The script each CLI demo feeds MockLLM (_SCRIPT) is byte-for-byte the
    scenario's mock_script — the SAME sequence the Web runner injects."""
    for scenario_id, module in _SCENARIO_ID_TO_CLI_MODULE.items():
        expected = list(get_scenario(scenario_id).mock_script)
        assert module._SCRIPT == expected, (
            f"CLI demo for {scenario_id} diverged from the shared mock_script"
        )


def test_cli_and_web_share_success_conditions(tmp_path):
    """The SAME success_conditions that gate the WebUI verdict also gate make
    demo. Running each scenario through the Web DemoRunManager (sync) must yield
    all-passed acceptance for exactly the scenarios make demo also passes — so a
    WebUI 'success' can never disagree with a `make demo` pass/fail."""
    from aegiscode.demo.service import DemoRunManager

    # For the interactive scenario, approve every request synchronously so the
    # non-interactive harness path still exercises the real approval + supersede
    # state machine (round 1 approved, round 2 mutated → SUPERSEDED).
    mgr = DemoRunManager(
        allowed_base=str(tmp_path),
        db_path=str(tmp_path / "consistency.db"),
        sync=True,
        sync_decision_fn=lambda _approval_id: True,
    )
    for scenario_id in REGISTRY:
        run_id = mgr.start_run(scenario_id)
        run = mgr.get_run(run_id)
        assert run["done"] is True, f"{scenario_id} did not reach terminal state"
        passed = {c["key"]: c["passed"] for c in run["acceptance"]}
        assert all(passed.values()), (
            f"Web run of {scenario_id} failed acceptance {passed} — this would be a "
            f"CLI/Web divergence (make demo asserts the same success_conditions)"
        )
