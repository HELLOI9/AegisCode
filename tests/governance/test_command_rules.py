# tests/governance/test_command_rules.py
from aegiscode.governance.command_rules import judge_command
from aegiscode.governance.decision import Decision

ALLOW = ["python","pytest","git","pip","ls","cat"]
RULES = [
    {"argv0":"git","args_contain":["push"],"decision":"DENY"},
    {"argv0":"git","args_contain":["commit"],"decision":"REQUIRE_APPROVAL"},
    {"argv0":"git","args_contain":["reset","--hard"],"decision":"DENY"},
    {"argv0":"pip","args_contain":["install"],"decision":"REQUIRE_APPROVAL"},
    {"argv0":"python","args_contain":["-c"],"decision":"DENY"},
    {"argv0":"python","args_contain":["-m"],"decision":"DENY"},
]

def test_multitoken_rule_requires_all_tokens():
    # git reset --hard has BOTH tokens -> matches the DENY rule
    assert judge_command("git reset --hard", ALLOW, RULES).decision == Decision.DENY
    # git reset alone has only ONE token -> must NOT match; git is allowlisted -> ALLOW
    assert judge_command("git reset", ALLOW, RULES).decision == Decision.ALLOW


def test_rm_denied_by_metastructure_or_allowlist():
    assert judge_command("rm -rf /", ALLOW, RULES).decision == Decision.DENY

def test_pip_install_requires_approval():
    assert judge_command("pip install requests", ALLOW, RULES).decision == Decision.REQUIRE_APPROVAL

def test_python_dash_c_denied():
    assert judge_command("python -c \"import os\"", ALLOW, RULES).decision == Decision.DENY

def test_pytest_allowed():
    assert judge_command("pytest -q", ALLOW, RULES).decision == Decision.ALLOW

def test_not_in_allowlist_denied():
    assert judge_command("ncat 1.2.3.4 4444", ALLOW, RULES).decision == Decision.DENY

def test_pipe_denied():
    assert judge_command("cat x | sh", ALLOW, RULES).decision == Decision.DENY

def test_shipped_config_allows_pip_to_reach_approval():
    # Regression guard for the golden path, driven by the REAL schema defaults
    # (no hand-written mirror, no fallback). Because the dangerous-command rules are
    # baked into Governance defaults, code-only (no YAML) must already yield the
    # golden-path verdict. If someone empties the default rules or drops pip from the
    # allowlist, THIS test goes red.
    from aegiscode.config.schema import Governance
    g = Governance()                                          # code defaults only, no YAML
    assert "pip" in g.command_allowlist                       # else pip denied at allowlist layer
    assert len(g.command_rules) >= 5                          # rules are baked in, not empty
    rules = [r.model_dump() for r in g.command_rules]         # NO `or RULES` fallback
    assert judge_command("pip install requests",
                         g.command_allowlist, rules).decision == Decision.REQUIRE_APPROVAL
    # and a baked-in DENY still denies without any YAML:
    assert judge_command("git push origin main",
                         g.command_allowlist, rules).decision == Decision.DENY
