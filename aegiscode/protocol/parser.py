import json
import re
from pydantic import ValidationError
from aegiscode.protocol.action import Action


class ActionParseError(ValueError): ...


_FENCE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _last_balanced(text: str) -> str | None:
    stack, start = 0, None
    best = None
    for i, c in enumerate(text):
        if c == "{":
            if stack == 0:
                start = i
            stack += 1
        elif c == "}" and stack:
            stack -= 1
            if stack == 0:
                best = text[start : i + 1]
    return best


def parse_action(text: str) -> Action:
    m = _FENCE.search(text)
    raw = m.group(1) if m else _last_balanced(text)
    if not raw:
        raise ActionParseError("no JSON object found")
    try:
        data = json.loads(raw)
        return Action(**data)
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        raise ActionParseError(str(e))
