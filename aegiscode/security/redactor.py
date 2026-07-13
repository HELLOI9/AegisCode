# aegiscode/security/redactor.py
import re

_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(?:KEY|TOKEN|PASSWORD|SECRET)\s*=\s*[A-Za-z0-9\-_+/=]{16,}"),
]

def redact(text: str, workspace_root: str | None = None) -> str:
    out = text
    for p in _PATTERNS:
        out = p.sub("[REDACTED]", out)
    if workspace_root:
        root = workspace_root.rstrip("/")
        # strip "<root>/" -> "" so in-workspace paths become relative
        out = re.sub(re.escape(root) + r"/", "", out)
        # strip bare "<root>" only at a path boundary (/, end, whitespace, colon)
        out = re.sub(re.escape(root) + r"(?=/|$|[\s:])", "", out)
    return out
