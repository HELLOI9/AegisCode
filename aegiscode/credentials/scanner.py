import re
from dataclasses import dataclass

_PATTERNS = [re.compile(p) for p in [
    r"sk-ant-[A-Za-z0-9\-_]{20,}", r"sk-[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}", r"(?i)(KEY|TOKEN|SECRET|PASSWORD)\s*=\s*[A-Za-z0-9\-_+/=]{16,}"]]

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
        try: out += scan_text(open(p, encoding="utf-8", errors="ignore").read(), p)
        except OSError: continue
    return out
