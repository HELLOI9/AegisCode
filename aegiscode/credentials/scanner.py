import re
from dataclasses import dataclass

# Single source of truth: reuse the redactor's credential patterns so the CI
# secret-scan gate and the log/hash-chain redactor can never drift apart.
# (No import cycle: aegiscode.security.redactor imports only `re`.)
from aegiscode.security.redactor import KEY_PATTERNS

_PATTERNS = [re.compile(p) for p in KEY_PATTERNS]

@dataclass
class Finding:
    path: str; line_no: int; pattern: str

def scan_text(text, path="<text>"):
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for p in _PATTERNS:
            if p.search(line): out.append(Finding(path, i, p.pattern))
    return out

def scan_paths(paths):
    out = []
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="ignore") as fh:
                out += scan_text(fh.read(), p)
        except OSError:
            continue
    return out
