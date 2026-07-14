# tests/governance/test_command_bypass.py
# Red-team tests for four reproduced governance bypasses in judge_command:
#   C1 interpreter family not normalized (python3 escapes python -c/-m DENY)
#   C2 attached short options bypass token match (python -c'...' / -cFOO)
#   I1 long-option abbreviation bypass (git reset --h == --hard)
#   I2 first-match-wins lets an ALLOW rule shadow an overlapping DENY
from aegiscode.governance.command_rules import judge_command
from aegiscode.governance.decision import Decision

# Mirror of shipped defaults (argv0 + args_contain + decision), as dict rules.
ALLOW = ["python", "python3", "pip", "pytest", "ruff", "mypy", "git", "ls", "cat"]
RULES = [
    {"argv0": "git",    "args_contain": ["push"],            "decision": "DENY"},
    {"argv0": "git",    "args_contain": ["reset", "--hard"], "decision": "DENY"},
    {"argv0": "git",    "args_contain": ["clean"],           "decision": "DENY"},
    {"argv0": "git",    "args_contain": ["commit"],          "decision": "REQUIRE_APPROVAL"},
    {"argv0": "pip",    "args_contain": ["install"],         "decision": "REQUIRE_APPROVAL"},
    {"argv0": "python", "args_contain": ["-c"],              "decision": "DENY"},
    {"argv0": "python", "args_contain": ["-m"],              "decision": "DENY"},
]


# ---- C1: interpreter family normalization -------------------------------
def test_c1_python3_dash_m_denied():
    assert judge_command("python3 -m http.server", ALLOW, RULES).decision == Decision.DENY

def test_c1_python3_dash_c_denied_no_metachars():
    # `pass` has no shell metachars, so it survives the lexer and must hit the -c DENY.
    assert judge_command("python3 -c pass", ALLOW, RULES).decision == Decision.DENY

def test_c1_python3x_versioned_denied():
    assert judge_command("python3.12 -m http.server", ALLOW, RULES).decision == Decision.DENY

def test_c1_python3_script_not_denied_by_dashc_rule():
    # NON-regression: no -c/-m present -> consistent with `python script.py` (ALLOW).
    assert judge_command("python3 script.py", ALLOW, RULES).decision == Decision.ALLOW
    assert judge_command("python script.py", ALLOW, RULES).decision == Decision.ALLOW


# ---- C2: attached short options -----------------------------------------
def test_c2_attached_dash_c_quoted_denied():
    assert judge_command("python -c'import os'", ALLOW, RULES).decision == Decision.DENY

def test_c2_attached_dash_c_bareword_denied():
    # metachar-free attached form: `-cpass` survives the lexer, must hit -c DENY.
    assert judge_command("python -cpass", ALLOW, RULES).decision == Decision.DENY

def test_c2_attached_option_nonregression_pip_quiet():
    # An attached/long option elsewhere must not disturb a normal positional match.
    assert judge_command("pip install --quiet requests", ALLOW, RULES).decision == Decision.REQUIRE_APPROVAL


# ---- I1: long-option abbreviation ---------------------------------------
def test_i1_git_reset_dash_h_abbrev_denied():
    assert judge_command("git reset --h", ALLOW, RULES).decision == Decision.DENY

def test_i1_git_reset_hard_eq_denied():
    assert judge_command("git reset --hard=/x", ALLOW, RULES).decision == Decision.DENY

def test_i1_git_reset_soft_not_overmatched():
    # NON-regression: --soft must NOT be swallowed by the --hard rule.
    assert judge_command("git reset --soft", ALLOW, RULES).decision == Decision.ALLOW


# ---- I2: DENY must dominate over ordering --------------------------------
def test_i2_deny_dominates_allow_ordering():
    # ALLOW listed BEFORE an overlapping DENY: DENY must still win.
    rules = [
        {"argv0": "git", "args_contain": ["push"], "decision": "ALLOW"},
        {"argv0": "git", "args_contain": ["push"], "decision": "DENY"},
    ]
    assert judge_command("git push origin main", ALLOW, rules).decision == Decision.DENY

def test_i2_precedence_ladder():
    # REQUIRE_APPROVAL beats ALLOW_WITH_AUDIT beats ALLOW when all match.
    rules = [
        {"argv0": "git", "args_contain": ["commit"], "decision": "ALLOW"},
        {"argv0": "git", "args_contain": ["commit"], "decision": "ALLOW_WITH_AUDIT"},
        {"argv0": "git", "args_contain": ["commit"], "decision": "REQUIRE_APPROVAL"},
    ]
    assert judge_command("git commit -q", ALLOW, rules).decision == Decision.REQUIRE_APPROVAL

def test_i2_non_overlapping_rules_unaffected():
    # Distinct commands keep their own verdicts (no cross-contamination).
    assert judge_command("pip install requests", ALLOW, RULES).decision == Decision.REQUIRE_APPROVAL
    assert judge_command("pytest -q", ALLOW, RULES).decision == Decision.ALLOW
