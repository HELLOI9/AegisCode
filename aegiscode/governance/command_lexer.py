# aegiscode/governance/command_lexer.py
import shlex
from typing import NamedTuple

class LexResult(NamedTuple):
    ok: bool; argv: list; reason: str; has_metastructure: bool

_META = ["&&", "||", "$(", ">>", "|", ">", "<", ";", "`", "&", "(", ")",
         "*", "?", "[", "{", "\n", "\r"]

def lex_command(command: str) -> LexResult:
    for token in _META:
        if token in command:
            return LexResult(False, [], f"shell metastructure {token!r} not allowed", True)
    try:
        argv = shlex.split(command)
    except ValueError as e:
        return LexResult(False, [], f"lex error: {e}", False)
    if not argv:
        return LexResult(False, [], "empty command", False)
    return LexResult(True, argv, "ok", False)
