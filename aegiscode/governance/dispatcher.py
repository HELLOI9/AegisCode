# aegiscode/governance/dispatcher.py
import fnmatch
import os
import re

from aegiscode.governance.approval import SupersededError, validate_resume
from aegiscode.governance.command_lexer import lex_command
from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import GovernanceVerdict
from aegiscode.governance.path_fence import check_path
from aegiscode.tools.result import ToolResult

_FILE_TOOLS = {"read_file", "write_file", "list_files", "search_text"}


# Commands whose POSITIONAL argument is a file the process reads/executes — for
# these, a bare token whose name matches a sensitive pattern (e.g. `python .env`,
# `pytest key.pem`) is a genuine read/exec of a secret and must be fenced even
# with no slash. For every OTHER allowlisted command (git, pip), a bare token is
# a ref / commit message / package name, NOT a file access, so a name that
# merely CONTAINS a sensitive word ("added-credentials-helper", "feature/
# credentials") must NOT be hard-denied by the fence — it goes to the policy
# engine for its normal verdict. (Escapes are still denied for ALL commands.)
_FILE_CONSUMING_ARGV0 = re.compile(r"^(python\d?[\d.]*|pytest|ruff|mypy)$")


def _looks_like_path(token):
    """True if a token references a filesystem location (has a path separator).

    Absolute, explicitly-relative, or any token containing "/". Bare flags and
    bare words are NOT path-like here — the sensitive-NAME case (no slash) is
    handled separately and only for file-consuming commands.
    """
    return token.startswith(("/", "./", "../")) or "/" in token


def _fence_command(command, root, sensitive_patterns):
    """Return a reason string if a token in `command` fails the path fence, else None.

    Two distinct threats, deliberately scoped differently:
      * ESCAPE (path resolves outside the workspace) — a threat for ANY command,
        always denied.
      * SENSITIVE NAME (an in-workspace token whose basename matches a sensitive
        pattern, e.g. `.env`/`*.pem`) — a read/exec threat only when the command
        CONSUMES that token as a file (python/pytest/ruff/mypy). For git/pip a
        bare sensitive-WORD token is a ref/message/package, not a file, so we do
        NOT fence it (it still gets the policy engine's verdict).
    A leading `--opt=` is stripped so the value part is checked too.
    """
    lex = lex_command(command)
    if not lex.ok:
        # Metastructure / lex failure is the command judge's job, not the fence.
        return None
    argv0 = lex.argv[0] if lex.argv else ""
    file_consuming = bool(_FILE_CONSUMING_ARGV0.match(argv0))
    for token in lex.argv[1:]:
        candidate = token
        if token.startswith("--") and "=" in token:
            candidate = token.split("=", 1)[1]  # check the value after --opt=

        path_like = _looks_like_path(candidate)
        sensitive_name = any(
            fnmatch.fnmatch(os.path.basename(candidate), pat)
            for pat in sensitive_patterns
        )
        if not path_like and not sensitive_name:
            continue

        pv = check_path(candidate, root, sensitive_patterns)
        if pv.allowed:
            continue
        # Escape reasons apply to every command. A pure sensitive-NAME denial
        # (path stays in-workspace) is enforced only for file-consuming commands.
        is_escape = "escape" in pv.reason or "outside workspace" in pv.reason
        if is_escape or file_consuming:
            return pv.reason
    return None


class Dispatcher:
    def __init__(self, registry, engine, path_config):
        self.registry = registry
        self.engine = engine
        self.pc = path_config

    def _run_command_fence_reason(self, action, ctx):
        """None if action is not a fence-violating run_command, else the reason."""
        if action.tool != "run_command":
            return None
        command = action.arguments.get("command", "")
        if not command:
            return None
        root = getattr(ctx, "workspace_root", None) or self.pc.workspace_root
        return _fence_command(command, root, self.pc.sensitive_patterns)

    def dispatch(self, action, ctx):
        tool = self.registry.get(action.tool)
        if tool is None:
            return (
                GovernanceVerdict(Decision.DENY, "UNKNOWN_TOOL", "unknown tool"),
                ToolResult(
                    tool=action.tool,
                    status="error",
                    category="INVALID_ACTION",
                    summary=f"unknown tool {action.tool}",
                ),
            )

        # Path fence: run before policy engine for all file tools that carry a path arg.
        if action.tool in _FILE_TOOLS and "path" in action.arguments:
            # Anchor the fence to the workspace the tool ACTUALLY runs in
            # (per-task ctx.workspace_root). config.workspace.root is frozen at
            # build time and diverges from the real workspace on host `run
            # --workspace` and on `serve`; using it would fence a nonexistent
            # path and miss in-workspace symlinks to sensitive files. Fall back
            # to pc.workspace_root when ctx carries no workspace_root.
            root = getattr(ctx, "workspace_root", None) or self.pc.workspace_root
            pv = check_path(
                action.arguments["path"],
                root,
                self.pc.sensitive_patterns,
            )
            if not pv.allowed:
                return (
                    GovernanceVerdict(Decision.DENY, "PATH_FENCE", pv.reason),
                    ToolResult(
                        tool=action.tool,
                        status="denied",
                        category="POLICY_DENIED",
                        summary=pv.reason,
                    ),
                )

        # run_command path fence: even an allowlisted command must not reference
        # a path that escapes the workspace or matches a sensitive pattern
        # (defect C3 — `cat /etc/passwd` / `cat .env` sidestepped the file fence).
        cmd_reason = self._run_command_fence_reason(action, ctx)
        if cmd_reason is not None:
            return (
                GovernanceVerdict(Decision.DENY, "CMD_PATH_FENCE", cmd_reason),
                ToolResult(
                    tool=action.tool,
                    status="denied",
                    category="POLICY_DENIED",
                    summary=cmd_reason,
                ),
            )

        # Policy engine evaluation — guard against matcher bugs.
        try:
            verdict = self.engine.evaluate(action, ctx)
        except Exception as exc:  # noqa: BLE001
            return (
                GovernanceVerdict(Decision.DENY, "INTERNAL_ERROR", str(exc)),
                ToolResult(
                    tool=action.tool,
                    status="error",
                    category="INTERNAL_ERROR",
                    summary=f"policy engine error: {exc}",
                ),
            )

        if verdict.decision == Decision.DENY:
            return (
                verdict,
                ToolResult(
                    tool=action.tool,
                    status="denied",
                    category="POLICY_DENIED",
                    summary=verdict.reason,
                ),
            )

        if verdict.decision == Decision.REQUIRE_APPROVAL:
            return (verdict, None)

        # ALLOW or ALLOW_WITH_AUDIT — execute.
        return (verdict, tool.run(action.arguments, ctx))

    def execute_approved(self, action, ctx, approved_fp=None):
        """Bypass the governance gate and directly execute an already-approved action.

        Used after REQUIRE_APPROVAL has been resolved in favour of approval.
        Returns ToolResult from the tool's run method.

        approval binding: when *approved_fp* is supplied it is the fingerprint of
        the action at the moment approval was granted. If the action about to run
        no longer matches it (tool name / path / any argument changed), the old
        approval is SUPERSEDED — the modified action MUST NOT execute. We reuse
        approval.validate_resume/SupersededError (the canonical mechanism) and
        fail closed with a denied ToolResult flagged artifacts["superseded"]=True
        so the caller can re-evaluate the changed action instead of running it.
        """
        if approved_fp is not None:
            try:
                validate_resume(approved_fp, action)
            except SupersededError as exc:
                return ToolResult(
                    tool=action.tool,
                    status="denied",
                    category="POLICY_DENIED",
                    summary=f"SUPERSEDED: {exc}",
                    artifacts={"superseded": True},
                )

        tool = self.registry.get(action.tool)
        if tool is None:
            return ToolResult(
                tool=action.tool,
                status="error",
                category="INVALID_ACTION",
                summary=f"unknown tool {action.tool}",
            )

        # Path fence is a workspace-safety invariant, NOT a policy decision:
        # even an approved write must never escape the workspace or touch a
        # sensitive file. Re-check the same fence that dispatch() runs.
        if action.tool in _FILE_TOOLS and "path" in action.arguments:
            root = getattr(ctx, "workspace_root", None) or self.pc.workspace_root
            pv = check_path(
                action.arguments["path"],
                root,
                self.pc.sensitive_patterns,
            )
            if not pv.allowed:
                return ToolResult(
                    tool=action.tool,
                    status="denied",
                    category="POLICY_DENIED",
                    summary=pv.reason,
                )

        # run_command fence is likewise a workspace-safety invariant: even an
        # approved command must not reference an escaping/sensitive path.
        cmd_reason = self._run_command_fence_reason(action, ctx)
        if cmd_reason is not None:
            return ToolResult(
                tool=action.tool,
                status="denied",
                category="POLICY_DENIED",
                summary=cmd_reason,
            )

        return tool.run(action.arguments, ctx)
