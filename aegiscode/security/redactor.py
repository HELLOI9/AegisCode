# aegiscode/security/redactor.py
import re

# Credential detection patterns -- SINGLE SOURCE OF TRUTH. The credential
# scanner (aegiscode/credentials/scanner.py) imports KEY_PATTERNS from here so
# the redactor (defense-in-depth scrub before logs/hash-chain/feedback/memory)
# and the CI secret-scan gate can never drift apart.
#
# OpenAI keys: the modern dominant formats sk-proj-... and sk-svcacct-...
# contain hyphens and underscores, so the char class must include `_-`. This
# single pattern also subsumes the legacy sk-<alnum> keys and Anthropic's
# sk-ant-... keys. The {20,} bound keeps ordinary hyphenated words (e.g.
# "sk-short", "task-list-view") from being over-redacted.
OPENAI_KEY = r"sk-[A-Za-z0-9_-]{20,}"
AWS_KEY = r"AKIA[0-9A-Z]{16}"
# Generic assignment: an optional quote after `=` so that KEY = "..." and
# SECRET='...' are caught -- previously a quote broke the match entirely.
GENERIC_ASSIGNMENT = (
    r"(?i)(?:KEY|TOKEN|PASSWORD|SECRET)\s*=\s*['\"]?[A-Za-z0-9\-_+/=]{16,}"
)

KEY_PATTERNS = [OPENAI_KEY, AWS_KEY, GENERIC_ASSIGNMENT]

_PATTERNS = [re.compile(p) for p in KEY_PATTERNS]

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
