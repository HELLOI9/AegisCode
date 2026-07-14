# aegiscode/governance/factory.py
"""
Governance factory — wires config-driven defaults into PolicyEngine + Dispatcher.

Three public builders:
  build_default_fn(config)      -> Callable used as PolicyEngine.default_fn
  build_engine(config)          -> PolicyEngine(rules=[], default_fn=...)
  build_path_config(config)     -> SimpleNamespace(workspace_root, sensitive_patterns)
  build_dispatcher(config, reg) -> Dispatcher ready to use
"""
from __future__ import annotations

import types
from typing import Callable

from aegiscode.governance.command_rules import judge_command
from aegiscode.governance.decision import Decision
from aegiscode.governance.dispatcher import Dispatcher
from aegiscode.governance.engine import GovernanceVerdict, PolicyEngine

_READONLY_TOOLS = {"read_file", "list_files", "search_text"}


def build_default_fn(config) -> Callable:
    """Return the fail-closed default tier function for PolicyEngine.default_fn."""

    # Snapshot config values at build time so the closure is self-contained.
    command_allowlist = list(config.governance.command_allowlist)
    command_rules = [r.model_dump() for r in config.governance.command_rules]
    # Normalize: ensure every entry ends with "/" so "src" can't match "src_evil/".
    write_allowlist_dirs = [
        d if d.endswith("/") else d + "/" for d in config.governance.write_allowlist_dirs
    ]
    default_decisions = config.governance.default_decisions

    def _default_fn(action, ctx) -> GovernanceVerdict:
        tool = action.tool

        # --- run_command: delegate to the full command pipeline (dynamic verdict) ---
        if tool == "run_command":
            command = action.arguments.get("command", "")
            return judge_command(command, command_allowlist, command_rules)

        # --- finish: always allow (agent signalling completion) ---
        if tool == "finish":
            return GovernanceVerdict(Decision.ALLOW, "TIER_FINISH", "finish action always allowed")

        # --- run_tests: feedback sensor (SPEC §6) — read-only observation of
        # test state via a fixed command, not an external-world mutation. It is
        # the feedback sensor and MUST be allowed to execute. ---
        if tool == "run_tests":
            return GovernanceVerdict(
                Decision.ALLOW,
                "TIER_SENSOR",
                "run_tests is the feedback sensor → always allowed to execute",
            )

        # --- readonly tools ---
        if tool in _READONLY_TOOLS:
            decision = default_decisions.readonly
            return GovernanceVerdict(decision, "TIER_READONLY", f"readonly tool {tool!r} → {decision.value}")

        # --- write_file: check write_allowlist_dirs first ---
        if tool == "write_file":
            path = action.arguments.get("path", "")
            for allowed_dir in write_allowlist_dirs:
                if path.startswith(allowed_dir):
                    return GovernanceVerdict(
                        Decision.ALLOW,
                        "TIER_WRITE_ALLOWLISTED",
                        f"write path {path!r} is under allowlisted dir {allowed_dir!r}",
                    )
            decision = default_decisions.write
            return GovernanceVerdict(
                decision,
                "TIER_WRITE",
                f"write path {path!r} not in write_allowlist_dirs → {decision.value}",
            )

        # --- fail-closed catch-all ---
        decision = default_decisions.command
        return GovernanceVerdict(
            decision,
            "TIER_DEFAULT",
            f"tool {tool!r} not recognised → fail-closed {decision.value}",
        )

    return _default_fn


def build_engine(config) -> PolicyEngine:
    """Build a PolicyEngine with empty static rules and the config-driven default_fn."""
    return PolicyEngine(rules=[], default_fn=build_default_fn(config))


def build_path_config(config):
    """Return a SimpleNamespace that Dispatcher reads for path-fence checks."""
    return types.SimpleNamespace(
        workspace_root=config.workspace.root,
        sensitive_patterns=config.governance.sensitive_file_patterns,
    )


def build_dispatcher(config, registry) -> Dispatcher:
    """Build a fully-wired Dispatcher from an AegisConfig and a ToolRegistry."""
    return Dispatcher(
        registry=registry,
        engine=build_engine(config),
        path_config=build_path_config(config),
    )
