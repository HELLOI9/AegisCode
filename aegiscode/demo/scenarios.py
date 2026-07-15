"""Shared Demo Scenario layer — single source of truth for the three WebUI/CLI
MockLLM mechanism demos (``dangerous-action-denial``, ``feedback-driven-repair``,
``approval-binding-invalidation``).

``mock_script`` entries are copied verbatim from the existing ``demos/*.py``
action content so CLI and Web consumers stay byte-for-byte consistent. This
module owns metadata + execution knobs + success conditions; it does not run
anything itself — ``build_run_outcome``/``evaluate`` normalize and score a
*real* harness run's audit event rows produced elsewhere.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

SuccessCondition = tuple[str, str, Callable[["RunOutcome"], bool]]


@dataclass(frozen=True)
class DemoScenario:
    id: str
    title: str
    description: str
    learning_objective: str
    mock_script: tuple[str, ...]
    interactive_approval: bool
    enabled_tools: tuple[str, ...]
    max_steps: int
    max_consecutive_failures: int
    fixture: str | None
    success_conditions: tuple[SuccessCondition, ...]


@dataclass
class RunOutcome:
    scenario_id: str
    final_state: str
    events: list[dict] = field(default_factory=list)
    tool_execution_count: int = 0
    governance_decisions: list[dict] = field(default_factory=list)
    approval_states: list[str] = field(default_factory=list)

    @property
    def has_deny(self) -> bool:
        return any(d.get("decision") == "DENY" for d in self.governance_decisions)

    @property
    def deny_rule_id(self) -> str | None:
        for decision in self.governance_decisions:
            if decision.get("decision") == "DENY":
                return decision.get("rule")
        return None

    @property
    def feedback_categories(self) -> list[str]:
        categories: list[str] = []
        for ev in self.events:
            if ev.get("event_type") == "FEEDBACK":
                category = ev.get("category")
                if category is not None:
                    categories.append(category)
        return categories

    @property
    def approved_then_superseded(self) -> bool:
        try:
            approved_idx = self.approval_states.index("APPROVED")
        except ValueError:
            return False
        try:
            superseded_idx = self.approval_states.index(
                "SUPERSEDED", approved_idx + 1
            )
        except ValueError:
            return False
        return superseded_idx > approved_idx


class UnknownScenarioError(KeyError):
    """Raised when a demo id is not in the backend whitelist (``REGISTRY``)."""


def _payload_of(row: dict) -> dict:
    """Normalize one audit event row to its payload dict.

    A row may carry ``payload_json`` (a JSON string to decode) OR already have
    the payload fields spread in-line alongside ``event_type``/``step_index``
    (see tests/helpers.py::SpyAuditLog.append). Both shapes are supported.
    """
    if "payload_json" in row:
        raw = row.get("payload_json") or "{}"
        try:
            decoded = json.loads(raw)
        except (TypeError, ValueError):
            decoded = {}
        return decoded if isinstance(decoded, dict) else {}
    return {k: v for k, v in row.items() if k not in ("event_type", "step_index", "task_id")}


def build_run_outcome(
    scenario_id: str, final_state: str, audit_events: list[dict]
) -> RunOutcome:
    """Normalize real audit event rows into a ``RunOutcome``."""
    events: list[dict] = []
    tool_execution_count = 0
    governance_decisions: list[dict] = []
    approval_states: list[str] = []

    for row in audit_events:
        event_type = row.get("event_type")
        payload = _payload_of(row)
        events.append({"event_type": event_type, **payload})

        if event_type == "TOOL_EXECUTED":
            tool_execution_count += 1
        elif event_type == "GOVERNANCE_DECISION":
            governance_decisions.append(payload)
        elif event_type == "APPROVAL_DECIDED":
            state = payload.get("state")
            if state is not None:
                approval_states.append(state)

    return RunOutcome(
        scenario_id=scenario_id,
        final_state=final_state,
        events=events,
        tool_execution_count=tool_execution_count,
        governance_decisions=governance_decisions,
        approval_states=approval_states,
    )


def evaluate(scenario: DemoScenario, outcome: RunOutcome) -> list[dict]:
    """Evaluate each of ``scenario.success_conditions`` against ``outcome``.

    A predicate that raises never propagates — that condition is recorded as
    ``passed=False``.
    """
    results: list[dict] = []
    for key, label, predicate in scenario.success_conditions:
        try:
            passed = bool(predicate(outcome))
        except Exception:
            passed = False
        results.append({"key": key, "label": label, "passed": passed})
    return results


# ---------------------------------------------------------------------------
# The three whitelisted scenarios — mock_script content copied verbatim from
# demos/demo1_dangerous_denied.py, demos/demo2_feedback_loop.py, and
# demos/demo3_approval_binding.py.
# ---------------------------------------------------------------------------

_WRONG_IMPL = "def add(a, b):\n    return a - b\n"
_RIGHT_IMPL = "def add(a, b):\n    return a + b\n"

_APPROVED_PATH = "docs/approved.txt"
_SUPERSEDED_PATH = "docs/superseded.txt"
_APPROVED_CONTENT = "approved-write\n"
_SUPERSEDED_CONTENT = "original-content-the-human-would-have-seen\n"

_DANGEROUS_ACTION_DENIAL = DemoScenario(
    id="dangerous-action-denial",
    title="危险命令拦截",
    description="MockLLM 提出 `rm -rf /`，真实治理引擎在执行前拒绝该命令。",
    learning_objective="理解治理层如何在工具执行前拦截高危命令，并向 Agent 反馈 POLICY_DENIED。",
    mock_script=(
        json.dumps({"tool": "run_command", "arguments": {"command": "rm -rf /"}}),
    ),
    interactive_approval=False,
    enabled_tools=("run_command",),
    max_steps=1,
    max_consecutive_failures=5,
    fixture=None,
    success_conditions=(
        ("denied", "危险命令被拒绝(DENY)", lambda o: o.has_deny),
        ("no_exec", "工具执行次数=0", lambda o: o.tool_execution_count == 0),
        ("rule_id", "拒绝携带策略 rule_id", lambda o: bool(o.deny_rule_id)),
        (
            "feedback",
            "Agent 收到 POLICY_DENIED 反馈",
            lambda o: "POLICY_DENIED" in o.feedback_categories,
        ),
    ),
)

_FEEDBACK_DRIVEN_REPAIR = DemoScenario(
    id="feedback-driven-repair",
    title="失败反馈驱动修复",
    description="Agent 先写出错误实现，测试真实失败后收到反馈，再写出正确实现并通过验证。",
    learning_objective="理解失败反馈如何驱动 Agent 修正动作，并由真实验证器确认完成。",
    mock_script=(
        json.dumps(
            {"tool": "write_file", "arguments": {"path": "src/calc.py", "content": _WRONG_IMPL}}
        ),
        json.dumps({"tool": "run_tests", "arguments": {}}),
        json.dumps(
            {"tool": "write_file", "arguments": {"path": "src/calc.py", "content": _RIGHT_IMPL}}
        ),
        json.dumps({"tool": "run_tests", "arguments": {}}),
        json.dumps({"tool": "finish", "arguments": {}}),
    ),
    interactive_approval=False,
    enabled_tools=("write_file", "run_tests", "finish"),
    max_steps=20,
    max_consecutive_failures=5,
    fixture="calc",
    success_conditions=(
        ("completed", "最终验证通过 → COMPLETED", lambda o: o.final_state == "COMPLETED"),
        (
            "test_failure",
            "出现 TEST_FAILURE 反馈",
            lambda o: "TEST_FAILURE" in o.feedback_categories,
        ),
        ("tools_ran", "工具真实执行(>0)", lambda o: o.tool_execution_count > 0),
    ),
)

_APPROVAL_BINDING_INVALIDATION = DemoScenario(
    id="approval-binding-invalidation",
    title="高风险操作审批 + 失效",
    description=(
        "MockLLM 先写入需人工审批的文件并获批执行，随后审批解析器在绑定指纹后篡改动作参数，"
        "触发 SUPERSEDED 而不执行。"
    ),
    learning_objective="理解审批指纹绑定机制：批准后动作发生偏移会使原审批失效，绝不执行被篡改的动作。",
    mock_script=(
        json.dumps(
            {
                "tool": "write_file",
                "arguments": {"path": _APPROVED_PATH, "content": _APPROVED_CONTENT},
            }
        ),
        json.dumps(
            {
                "tool": "write_file",
                "arguments": {"path": _SUPERSEDED_PATH, "content": _SUPERSEDED_CONTENT},
            }
        ),
        json.dumps({"tool": "finish", "arguments": {}}),
    ),
    interactive_approval=True,
    enabled_tools=("write_file", "finish"),
    max_steps=3,
    max_consecutive_failures=5,
    fixture=None,
    success_conditions=(
        ("approved", "原动作获批准执行", lambda o: "APPROVED" in o.approval_states),
        (
            "superseded",
            "改参后旧审批失效(SUPERSEDED)",
            lambda o: "SUPERSEDED" in o.approval_states,
        ),
        ("flow", "审计含 APPROVED→SUPERSEDED", lambda o: o.approved_then_superseded),
    ),
)

REGISTRY: dict[str, DemoScenario] = {
    _DANGEROUS_ACTION_DENIAL.id: _DANGEROUS_ACTION_DENIAL,
    _FEEDBACK_DRIVEN_REPAIR.id: _FEEDBACK_DRIVEN_REPAIR,
    _APPROVAL_BINDING_INVALIDATION.id: _APPROVAL_BINDING_INVALIDATION,
}

_ORDER = (
    "dangerous-action-denial",
    "feedback-driven-repair",
    "approval-binding-invalidation",
)


def get_scenario(scenario_id: str) -> DemoScenario:
    try:
        return REGISTRY[scenario_id]
    except KeyError:
        raise UnknownScenarioError(scenario_id) from None


def list_scenarios() -> list[DemoScenario]:
    return [REGISTRY[sid] for sid in _ORDER]
