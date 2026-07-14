# aegiscode/governance/command_rules.py
from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import GovernanceVerdict
from aegiscode.governance.command_lexer import lex_command

def judge_command(command, allowlist, rules) -> GovernanceVerdict:
    lr = lex_command(command)
    if not lr.ok:
        return GovernanceVerdict(Decision.DENY, "CMD_STRUCT", lr.reason)
    argv0, args = lr.argv[0], lr.argv[1:]
    if argv0 not in allowlist:
        return GovernanceVerdict(Decision.DENY, "CMD_ALLOWLIST", f"{argv0} not in allowlist")
    for i, rule in enumerate(rules):
        if rule["argv0"] == argv0 and all(tok in args for tok in rule["args_contain"]):
            dec = Decision(rule["decision"])
            return GovernanceVerdict(dec, f"CMD_RULE_{i}", f"rule matched: {argv0} {rule['args_contain']}")
    return GovernanceVerdict(Decision.ALLOW, "CMD_DEFAULT_ALLOWED", f"{argv0} allowed")
