# aegiscode/governance/path_fence.py
import os, fnmatch
from typing import NamedTuple


class PathVerdict(NamedTuple):
    allowed: bool
    reason: str


def _matches_sensitive(p, patterns):
    """Return True if path p matches any pattern in the sensitive list."""
    base = os.path.basename(p)
    segs = p.split(os.sep)
    for pat in patterns:
        if fnmatch.fnmatch(base, pat) or pat.rstrip("/") in segs:
            return True
    return False


def check_path(path, workspace_root, sensitive_patterns) -> PathVerdict:
    if not path or not isinstance(path, str):
        return PathVerdict(False, "empty or non-string path")
    root = os.path.realpath(workspace_root)
    joined = path if os.path.isabs(path) else os.path.join(root, path)
    if os.path.islink(joined) or os.path.exists(joined):
        real = os.path.realpath(joined)
    else:                                        # new file: fence the parent
        parent = os.path.realpath(os.path.dirname(joined))
        if os.path.commonpath([parent, root]) != root:
            return PathVerdict(False, "parent dir outside workspace")
        real = os.path.join(parent, os.path.basename(joined))
    if os.path.commonpath([os.path.realpath(real), root]) != root:
        return PathVerdict(False, "path escapes workspace (traversal/symlink)")
    # Check sensitive patterns on both the original input path AND the resolved
    # real path — an in-workspace symlink with an innocuous name pointing to a
    # sensitive file (e.g. report.txt -> .env) must be denied on the resolved path.
    if _matches_sensitive(path, sensitive_patterns) or _matches_sensitive(real, sensitive_patterns):
        # Find which pattern triggered for the error message
        base = os.path.basename(path)
        segs = path.split(os.sep)
        rbase = os.path.basename(real)
        rsegs = real.split(os.sep)
        for pat in sensitive_patterns:
            if (fnmatch.fnmatch(base, pat) or pat.rstrip("/") in segs
                    or fnmatch.fnmatch(rbase, pat) or pat.rstrip("/") in rsegs):
                return PathVerdict(False, f"sensitive file blocked: {pat}")
    return PathVerdict(True, "ok")
