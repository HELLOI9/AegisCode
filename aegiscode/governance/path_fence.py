# aegiscode/governance/path_fence.py
import os, fnmatch
from typing import NamedTuple


class PathVerdict(NamedTuple):
    allowed: bool
    reason: str


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
    base = os.path.basename(path)
    for pat in sensitive_patterns:
        if fnmatch.fnmatch(base, pat) or pat.rstrip("/") in path.split(os.sep):
            return PathVerdict(False, f"sensitive file blocked: {pat}")
    return PathVerdict(True, "ok")
