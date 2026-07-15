"""RED-first tests for the shared Demo Scenario layer (aegiscode/demo/scenarios.py).

Covers: REGISTRY whitelist, get_scenario/list_scenarios, scenario metadata
non-emptiness, mock_script parseability via aegiscode.protocol.parser.parse_action,
build_run_outcome normalization (both payload shapes), evaluate() semantics, and
RunOutcome.approved_then_superseded ordering.
"""
from __future__ import annotations

import json

import pytest

from aegiscode.protocol.parser import parse_action

from aegiscode.demo.scenarios import (
    REGISTRY,
    DemoScenario,
    RunOutcome,
    UnknownScenarioError,
    build_run_outcome,
    evaluate,
    get_scenario,
    list_scenarios,
)

_WHITELIST = (
    "dangerous-action-denial",
    "feedback-driven-repair",
    "approval-binding-invalidation",
)


class TestRegistry:
    def test_registry_contains_exactly_the_whitelisted_ids(self):
        assert set(REGISTRY.keys()) == set(_WHITELIST)

    def test_get_scenario_returns_scenario_for_known_id(self):
        for scenario_id in _WHITELIST:
            scenario = get_scenario(scenario_id)
            assert isinstance(scenario, DemoScenario)
            assert scenario.id == scenario_id

    def test_get_scenario_unknown_raises_unknown_scenario_error(self):
        with pytest.raises(UnknownScenarioError):
            get_scenario("nope")

    def test_unknown_scenario_error_is_a_key_error(self):
        assert issubclass(UnknownScenarioError, KeyError)

    def test_list_scenarios_stable_order_denial_feedback_approval(self):
        ids = [s.id for s in list_scenarios()]
        assert ids == list(_WHITELIST)


class TestScenarioMetadata:
    @pytest.mark.parametrize("scenario_id", _WHITELIST)
    def test_metadata_non_empty(self, scenario_id):
        scenario = get_scenario(scenario_id)
        assert scenario.title
        assert scenario.description
        assert scenario.learning_objective
        assert isinstance(scenario.enabled_tools, tuple)
        assert scenario.enabled_tools

    @pytest.mark.parametrize("scenario_id", _WHITELIST)
    def test_mock_script_is_non_empty_tuple(self, scenario_id):
        scenario = get_scenario(scenario_id)
        assert isinstance(scenario.mock_script, tuple)
        assert len(scenario.mock_script) > 0
        for entry in scenario.mock_script:
            assert isinstance(entry, str)

    @pytest.mark.parametrize("scenario_id", _WHITELIST)
    def test_mock_script_entries_are_valid_json(self, scenario_id):
        scenario = get_scenario(scenario_id)
        for entry in scenario.mock_script:
            json.loads(entry)  # must not raise

    @pytest.mark.parametrize("scenario_id", _WHITELIST)
    def test_mock_script_entries_parse_via_parse_action(self, scenario_id):
        scenario = get_scenario(scenario_id)
        for entry in scenario.mock_script:
            action = parse_action(entry)
            assert action.tool

    @pytest.mark.parametrize("scenario_id", _WHITELIST)
    def test_success_conditions_are_non_empty_tuple_of_key_label_predicate(
        self, scenario_id
    ):
        scenario = get_scenario(scenario_id)
        assert isinstance(scenario.success_conditions, tuple)
        assert len(scenario.success_conditions) > 0
        for cond in scenario.success_conditions:
            key, label, predicate = cond
            assert isinstance(key, str) and key
            assert isinstance(label, str) and label
            assert callable(predicate)

    def test_scenario_dataclass_is_frozen(self):
        scenario = get_scenario("dangerous-action-denial")
        with pytest.raises(Exception):
            scenario.title = "mutated"  # type: ignore[misc]


class TestScenarioSpecificMetadata:
    def test_dangerous_action_denial_knobs(self):
        scenario = get_scenario("dangerous-action-denial")
        assert scenario.enabled_tools == ("run_command",)
        assert scenario.max_steps == 1
        assert scenario.fixture is None
        assert scenario.interactive_approval is False
        assert len(scenario.mock_script) == 1
        action = parse_action(scenario.mock_script[0])
        assert action.tool == "run_command"
        assert action.arguments.get("command") == "rm -rf /"

    def test_feedback_driven_repair_knobs(self):
        scenario = get_scenario("feedback-driven-repair")
        assert scenario.enabled_tools == ("write_file", "run_tests", "finish")
        assert scenario.max_steps == 20
        assert scenario.fixture == "calc"
        assert scenario.interactive_approval is False
        assert len(scenario.mock_script) == 5
        tools = [parse_action(entry).tool for entry in scenario.mock_script]
        assert tools == ["write_file", "run_tests", "write_file", "run_tests", "finish"]
        first_write = parse_action(scenario.mock_script[0])
        assert first_write.arguments["path"] == "src/calc.py"
        assert "return a - b" in first_write.arguments["content"]
        second_write = parse_action(scenario.mock_script[2])
        assert "return a + b" in second_write.arguments["content"]

    def test_approval_binding_invalidation_knobs(self):
        scenario = get_scenario("approval-binding-invalidation")
        assert scenario.enabled_tools == ("write_file", "finish")
        assert scenario.max_steps == 3
        assert scenario.max_consecutive_failures == 5
        assert scenario.fixture is None
        assert scenario.interactive_approval is True
        assert len(scenario.mock_script) == 3
        tools = [parse_action(entry).tool for entry in scenario.mock_script]
        assert tools == ["write_file", "write_file", "finish"]
        first_write = parse_action(scenario.mock_script[0])
        assert first_write.arguments["path"] == "docs/approved.txt"
        second_write = parse_action(scenario.mock_script[1])
        assert second_write.arguments["path"] == "docs/superseded.txt"


# ---------------------------------------------------------------------------
# build_run_outcome — both audit-row payload shapes must normalize identically.
# ---------------------------------------------------------------------------

def _rows_payload_json_shape():
    """Rows shaped like demos/demo1_dangerous_denied.py reads them: payload_json str."""
    return [
        {
            "event_type": "GOVERNANCE_DECISION",
            "step_index": 0,
            "payload_json": json.dumps({"decision": "DENY", "rule": "CMD_PATH_FENCE"}),
        },
        {
            "event_type": "FEEDBACK",
            "step_index": 0,
            "payload_json": json.dumps({"category": "POLICY_DENIED"}),
        },
    ]


def _rows_spread_shape():
    """Rows shaped like tests/helpers.py::SpyAuditLog.append spreads them inline."""
    return [
        {
            "event_type": "GOVERNANCE_DECISION",
            "step_index": 0,
            "decision": "DENY",
            "rule": "CMD_PATH_FENCE",
        },
        {
            "event_type": "FEEDBACK",
            "step_index": 0,
            "category": "POLICY_DENIED",
        },
    ]


class TestBuildRunOutcomePayloadShapes:
    @pytest.mark.parametrize("rows_factory", [_rows_payload_json_shape, _rows_spread_shape])
    def test_governance_and_feedback_normalize_in_both_shapes(self, rows_factory):
        outcome = build_run_outcome(
            "dangerous-action-denial", "DENIED", rows_factory()
        )
        assert isinstance(outcome, RunOutcome)
        assert outcome.scenario_id == "dangerous-action-denial"
        assert outcome.final_state == "DENIED"
        assert outcome.tool_execution_count == 0
        assert len(outcome.governance_decisions) == 1
        assert outcome.governance_decisions[0]["decision"] == "DENY"
        assert outcome.governance_decisions[0]["rule"] == "CMD_PATH_FENCE"
        assert outcome.has_deny is True
        assert outcome.deny_rule_id == "CMD_PATH_FENCE"
        assert outcome.feedback_categories == ["POLICY_DENIED"]

    def test_tool_execution_count_counts_tool_executed_events(self):
        rows = [
            {"event_type": "TOOL_EXECUTED", "step_index": 0, "payload_json": json.dumps({})},
            {"event_type": "TOOL_EXECUTED", "step_index": 1, "payload_json": json.dumps({})},
            {"event_type": "GOVERNANCE_DECISION", "step_index": 1,
             "payload_json": json.dumps({"decision": "ALLOW"})},
        ]
        outcome = build_run_outcome("feedback-driven-repair", "COMPLETED", rows)
        assert outcome.tool_execution_count == 2
        assert outcome.has_deny is False
        assert outcome.deny_rule_id is None

    def test_approval_states_normalize_from_approval_decided_events(self):
        rows = [
            {"event_type": "APPROVAL_DECIDED", "step_index": 0,
             "payload_json": json.dumps({"state": "APPROVED"})},
            {"event_type": "APPROVAL_DECIDED", "step_index": 1,
             "state": "SUPERSEDED"},
        ]
        outcome = build_run_outcome("approval-binding-invalidation", "COMPLETED", rows)
        assert outcome.approval_states == ["APPROVED", "SUPERSEDED"]

    def test_deny_rule_id_reads_first_deny_decision_rule_key(self):
        rows = [
            {"event_type": "GOVERNANCE_DECISION", "step_index": 0,
             "payload_json": json.dumps({"decision": "ALLOW", "rule": "OTHER"})},
            {"event_type": "GOVERNANCE_DECISION", "step_index": 1,
             "payload_json": json.dumps({"decision": "DENY", "rule": "CMD_ALLOWLIST"})},
        ]
        outcome = build_run_outcome("dangerous-action-denial", "DENIED", rows)
        assert outcome.deny_rule_id == "CMD_ALLOWLIST"


class TestRunOutcomeApprovedThenSuperseded:
    def test_true_when_approved_strictly_before_superseded(self):
        outcome = RunOutcome(
            scenario_id="approval-binding-invalidation",
            final_state="COMPLETED",
            events=[],
            tool_execution_count=1,
            governance_decisions=[],
            approval_states=["APPROVED", "SUPERSEDED"],
        )
        assert outcome.approved_then_superseded is True

    def test_false_when_only_approved(self):
        outcome = RunOutcome(
            scenario_id="approval-binding-invalidation",
            final_state="COMPLETED",
            events=[],
            tool_execution_count=1,
            governance_decisions=[],
            approval_states=["APPROVED"],
        )
        assert outcome.approved_then_superseded is False

    def test_false_when_superseded_before_approved(self):
        outcome = RunOutcome(
            scenario_id="approval-binding-invalidation",
            final_state="COMPLETED",
            events=[],
            tool_execution_count=1,
            governance_decisions=[],
            approval_states=["SUPERSEDED", "APPROVED"],
        )
        assert outcome.approved_then_superseded is False

    def test_false_when_no_approval_events(self):
        outcome = RunOutcome(
            scenario_id="approval-binding-invalidation",
            final_state="RUNNING",
            events=[],
            tool_execution_count=0,
            governance_decisions=[],
            approval_states=[],
        )
        assert outcome.approved_then_superseded is False


# ---------------------------------------------------------------------------
# evaluate()
# ---------------------------------------------------------------------------

class TestEvaluate:
    def test_all_pass_on_satisfying_outcome_dangerous_action_denial(self):
        scenario = get_scenario("dangerous-action-denial")
        rows = [
            {"event_type": "GOVERNANCE_DECISION", "step_index": 0,
             "payload_json": json.dumps({"decision": "DENY", "rule": "CMD_PATH_FENCE"})},
            {"event_type": "FEEDBACK", "step_index": 0,
             "payload_json": json.dumps({"category": "POLICY_DENIED"})},
        ]
        outcome = build_run_outcome("dangerous-action-denial", "DENIED", rows)
        results = evaluate(scenario, outcome)
        assert results
        for r in results:
            assert r["passed"] is True
            assert set(r.keys()) == {"key", "label", "passed"}

    def test_per_condition_false_on_missing_events(self):
        scenario = get_scenario("dangerous-action-denial")
        outcome = build_run_outcome("dangerous-action-denial", "DENIED", [])
        results = evaluate(scenario, outcome)
        by_key = {r["key"]: r["passed"] for r in results}
        # No GOVERNANCE_DECISION/FEEDBACK events at all: these conditions must
        # read as False. "no_exec" (tool_execution_count == 0) is trivially
        # True on an empty event list, so it is intentionally excluded here.
        assert by_key["denied"] is False
        assert by_key["rule_id"] is False
        assert by_key["feedback"] is False

    def test_all_pass_on_satisfying_outcome_feedback_driven_repair(self):
        scenario = get_scenario("feedback-driven-repair")
        rows = [
            {"event_type": "TOOL_EXECUTED", "step_index": 0, "payload_json": json.dumps({})},
            {"event_type": "FEEDBACK", "step_index": 1,
             "payload_json": json.dumps({"category": "TEST_FAILURE"})},
        ]
        outcome = build_run_outcome("feedback-driven-repair", "COMPLETED", rows)
        results = evaluate(scenario, outcome)
        assert results
        for r in results:
            assert r["passed"] is True

    def test_all_pass_on_satisfying_outcome_approval_binding_invalidation(self):
        scenario = get_scenario("approval-binding-invalidation")
        rows = [
            {"event_type": "APPROVAL_DECIDED", "step_index": 0,
             "payload_json": json.dumps({"state": "APPROVED"})},
            {"event_type": "APPROVAL_DECIDED", "step_index": 1,
             "payload_json": json.dumps({"state": "SUPERSEDED"})},
        ]
        outcome = build_run_outcome("approval-binding-invalidation", "COMPLETED", rows)
        results = evaluate(scenario, outcome)
        assert results
        for r in results:
            assert r["passed"] is True

    def test_predicate_raising_yields_passed_false_not_propagated(self):
        def boom(outcome):
            raise RuntimeError("boom")

        scenario = DemoScenario(
            id="dangerous-action-denial",
            title="t",
            description="d",
            learning_objective="l",
            mock_script=('{"tool": "run_command", "arguments": {"command": "rm -rf /"}}',),
            interactive_approval=False,
            enabled_tools=("run_command",),
            max_steps=1,
            max_consecutive_failures=3,
            fixture=None,
            success_conditions=(("boom", "boom label", boom),),
        )
        outcome = build_run_outcome("dangerous-action-denial", "DENIED", [])
        results = evaluate(scenario, outcome)
        assert results == [{"key": "boom", "label": "boom label", "passed": False}]
