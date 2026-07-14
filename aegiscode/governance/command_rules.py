# aegiscode/governance/command_rules.py
import re
from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import GovernanceVerdict
from aegiscode.governance.command_lexer import lex_command

# --- argv normalization for RULE MATCHING ONLY (never mutates what executes) ---

# Interpreter-family collapse: python3 / python3.12 / python3.x are the SAME
# interpreter as `python` for the purpose of matching -c/-m DENY rules (C1). We
# only fold the spelling we compare against rule["argv0"]; the real argv0 is
# untouched and still runs verbatim.
_INTERP_FAMILY = re.compile(r"^(python)\d[\d.]*$")


def _norm_argv0(argv0: str) -> str:
    m = _INTERP_FAMILY.match(argv0)
    return m.group(1) if m else argv0


def _arg_matches(tok: str, arg: str) -> bool:
    # Positional / non-dash rule tokens stay EXACT-equality: no prefix or attach
    # magic, so `reset` can't accidentally prefix-match unrelated args.
    if not tok.startswith("-"):
        return arg == tok
    # Long option (--foo): match --foo, its --foo=value form, and unambiguous
    # abbreviations (I1) — an actual arg that is a >2-char prefix of the rule
    # token (e.g. --h / --ha for --hard). --soft won't match --hard because
    # "--hard" does not start with "--soft".
    if tok.startswith("--"):
        argname = arg.split("=", 1)[0]      # drop any =value before comparing
        if not argname.startswith("--"):
            return False
        return len(argname) > 2 and tok.startswith(argname)
    # Short option (-c): match standalone -c OR attached -cFOO (C2). Guard against
    # a long option sneaking in via startswith.
    return arg == tok or (arg.startswith(tok) and not arg.startswith("--"))


def _rule_matches(rule, norm_argv0, args) -> bool:
    if _norm_argv0(rule["argv0"]) != norm_argv0:
        return False
    # Every rule token must be satisfied by SOME arg (order-independent).
    return all(any(_arg_matches(tok, a) for a in args) for tok in rule["args_contain"])


# Most-restrictive-wins precedence (I2): DENY dominates regardless of list order.
_SEVERITY = {
    Decision.ALLOW: 0,
    Decision.ALLOW_WITH_AUDIT: 1,
    Decision.REQUIRE_APPROVAL: 2,
    Decision.DENY: 3,
}


def judge_command(command, allowlist, rules) -> GovernanceVerdict:
    lr = lex_command(command)
    if not lr.ok:
        return GovernanceVerdict(Decision.DENY, "CMD_STRUCT", lr.reason)
    argv0, args = lr.argv[0], lr.argv[1:]
    if argv0 not in allowlist:
        return GovernanceVerdict(Decision.DENY, "CMD_ALLOWLIST", f"{argv0} not in allowlist")
    norm = _norm_argv0(argv0)
    # Evaluate ALL matching rules; keep the most restrictive verdict (DENY >
    # REQUIRE_APPROVAL > ALLOW_WITH_AUDIT > ALLOW). An ALLOW listed before an
    # overlapping DENY can no longer shadow it.
    winner = None  # (severity, index, decision)
    for i, rule in enumerate(rules):
        if _rule_matches(rule, norm, args):
            dec = Decision(rule["decision"])
            sev = _SEVERITY[dec]
            if winner is None or sev > winner[0]:
                winner = (sev, i, dec, rule["args_contain"])
    if winner is not None:
        _, i, dec, contains = winner
        return GovernanceVerdict(dec, f"CMD_RULE_{i}", f"rule matched: {argv0} {contains}")
    return GovernanceVerdict(Decision.ALLOW, "CMD_DEFAULT_ALLOWED", f"{argv0} allowed")
