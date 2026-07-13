import json
import re
from pydantic import ValidationError
from aegiscode.protocol.action import Action


class ActionParseError(ValueError): ...


_FENCE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
_DECODER = json.JSONDecoder()


def _last_json_object(text: str) -> dict | None:
    """Return the LAST top-level JSON object in text, string-aware.

    Scans each '{' position and uses raw_decode (which respects JSON string
    escaping) to find valid objects; keeps the last one that parses to a dict.
    After a successful parse, advances past the end of that object so nested
    '{' positions inside it are not treated as independent candidates.
    """
    best = None
    idx = text.find("{")
    while idx != -1:
        try:
            obj, end = _DECODER.raw_decode(text, idx)
            if isinstance(obj, dict):
                best = obj
            # Jump past this object entirely — don't recurse into its internals
            idx = text.find("{", end)
        except json.JSONDecodeError:
            idx = text.find("{", idx + 1)
    return best


def parse_action(text: str) -> Action:
    m = _FENCE.search(text)
    if m:
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            raise ActionParseError(str(e)) from e
    else:
        data = _last_json_object(text)
        if data is None:
            raise ActionParseError("no JSON object found") from None
    try:
        return Action(**data)
    except (ValidationError, TypeError) as e:
        raise ActionParseError(str(e)) from e
