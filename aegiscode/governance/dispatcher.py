# aegiscode/governance/dispatcher.py
from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import GovernanceVerdict
from aegiscode.governance.path_fence import check_path
from aegiscode.tools.result import ToolResult

_FILE_TOOLS = {"read_file", "write_file", "list_files", "search_text"}


class Dispatcher:
    def __init__(self, registry, engine, path_config):
        self.registry = registry
        self.engine = engine
        self.pc = path_config

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

    def execute_approved(self, action, ctx):
        """Bypass the governance gate and directly execute an already-approved action.

        Used after REQUIRE_APPROVAL has been resolved in favour of approval.
        Returns ToolResult from the tool's run method.
        """
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

        return tool.run(action.arguments, ctx)
