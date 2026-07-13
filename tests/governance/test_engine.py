from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import PolicyEngine, PolicyRule, GovernanceVerdict
from aegiscode.protocol.action import Action

def _deny_rm(a, ctx): return a.tool == "run_command" and "rm" in a.arguments.get("command","")

def test_first_match_wins():
    rules = [PolicyRule("R-RM", _deny_rm, Decision.DENY, "no rm")]
    eng = PolicyEngine(rules, default_fn=lambda a,c: GovernanceVerdict(Decision.ALLOW,"DEFAULT","ok"))
    v = eng.evaluate(Action(tool="run_command", arguments={"command":"rm -rf /"}), None)
    assert v.decision == Decision.DENY and v.rule_id == "R-RM"

def test_falls_through_to_default():
    eng = PolicyEngine([], default_fn=lambda a,c: GovernanceVerdict(Decision.ALLOW,"DEFAULT","ok"))
    v = eng.evaluate(Action(tool="read_file", arguments={"path":"a"}), None)
    assert v.decision == Decision.ALLOW and v.rule_id == "DEFAULT"

def test_decision_is_canonical_config_enum():
    from aegiscode.config.schema import Decision as ConfigDecision
    assert Decision is ConfigDecision            # single source of truth
