from dataclasses import dataclass
from typing import Callable
from aegiscode.governance.decision import Decision


@dataclass
class GovernanceVerdict:
    decision: Decision
    rule_id: str
    reason: str


@dataclass
class PolicyRule:
    rule_id: str
    matcher: Callable
    decision: Decision
    reason: str


class PolicyEngine:
    def __init__(self, rules, default_fn):
        self.rules = rules
        self.default_fn = default_fn

    def evaluate(self, action, ctx) -> GovernanceVerdict:
        for r in self.rules:
            if r.matcher(action, ctx):
                return GovernanceVerdict(r.decision, r.rule_id, r.reason)
        return self.default_fn(action, ctx)
