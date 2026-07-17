"""aegiscode/service/assembly.py — production wiring of a real ApplicationService.

tests/helpers.py::make_service is the STRUCTURAL template; here we wire REAL
(non-spy) components: real ToolRegistry, real dispatcher, real LLM client, and a
real final_verifier that RE-RUNS the feedback test command (SPEC demo②: COMPLETED
is decided by the verifier going green, not by the LLM claiming success).
"""
from __future__ import annotations

import shlex
import subprocess
from types import SimpleNamespace

from aegiscode.audit.chain import AuditLog
from aegiscode.governance.factory import build_dispatcher
from aegiscode.llm.mock import MockLLM
from aegiscode.loop.harness import HarnessCore
from aegiscode.memory.store import MemoryStore
from aegiscode.persistence.db import open_db
from aegiscode.service.app_service import ApplicationService, _workspace_hash
from aegiscode.tools.command_tool import RunCommandTool
from aegiscode.tools.file_tools import (
    ListFilesTool,
    ReadFileTool,
    SearchTextTool,
    WriteFileTool,
)
from aegiscode.tools.finish_tool import FinishTool
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.run_tests_tool import RunTestsTool


class NoKeyError(RuntimeError):
    """Raised when a real LLM provider is selected but no API key is configured."""


def build_llm(config, credential_store):
    """Build an LLM client from config. mock => MockLLM; real => key required."""
    provider = config.llm.provider
    if provider == "mock":
        # No scripted responses: the harness handles exhaustion as LLM_ERROR.
        return MockLLM([])

    key = credential_store.get_key()
    if not key:
        raise NoKeyError("no API key configured; run `aegiscode key set`")

    if provider == "openai":
        from aegiscode.llm.openai_adapter import OpenAIAdapter

        return OpenAIAdapter(
            model=config.llm.model, api_key=key, base_url=config.llm.base_url
        )
    if provider == "anthropic":
        from aegiscode.llm.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(
            model=config.llm.model, api_key=key, base_url=config.llm.base_url
        )

    raise NoKeyError(f"unknown llm provider: {provider!r}")


def _build_registry(config) -> ToolRegistry:
    """Register only the tools listed in config.tools.enabled."""
    enabled = set(config.tools.enabled)
    reg = ToolRegistry()
    factory = {
        "write_file": WriteFileTool,
        "read_file": ReadFileTool,
        "list_files": ListFilesTool,
        "search_text": SearchTextTool,
        "finish": FinishTool,
    }
    for name, cls in factory.items():
        if name in enabled:
            reg.register(cls())
    if "run_command" in enabled:
        reg.register(
            RunCommandTool(
                allowlist=config.governance.command_allowlist,
                rules=[r.model_dump() for r in config.governance.command_rules],
                timeout_sec=config.limits.command_timeout_sec,
                output_max_bytes=config.limits.output_max_bytes,
            )
        )
    if "run_tests" in enabled:
        reg.register(
            RunTestsTool(
                test_command=config.feedback.test_command,
                timeout_sec=config.limits.command_timeout_sec,
                output_max_bytes=config.limits.output_max_bytes,
            )
        )
    return reg


def _make_final_verifier(config, workspace):
    """Return a verifier that re-runs the feedback test command in *workspace*.

    Returns True iff exit code == 0 (SPEC demo②). Any failure to run the command
    (missing binary, timeout) is treated as NOT verified (False) — fail closed.
    """
    cmd = config.feedback.test_command
    timeout = config.limits.command_timeout_sec

    def verify() -> bool:
        try:
            p = subprocess.run(
                shlex.split(cmd),
                shell=False,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (subprocess.SubprocessError, OSError):
            return False
        return p.returncode == 0

    return verify


def build_service(config, credential_store, db_path: str, sync: bool = False):
    """Assemble a real ApplicationService.

    Parameters
    ----------
    config : AegisConfig
    credential_store : CredentialStore
        Source for the LLM API key (real providers only).
    db_path : str
        Filesystem path for the sqlite database.
    sync : bool
        If True, create_task runs inline (blocking) — used by the CLI so a run
        terminates before the process exits.

    Raises
    ------
    NoKeyError
        If a real provider is selected but no key is configured.
    """
    conn = open_db(db_path)
    memory_store = MemoryStore(conn)
    registry = _build_registry(config)
    dispatcher = build_dispatcher(config, registry)
    llm = build_llm(config, credential_store)

    def harness_factory(
        task_id, workspace, approval_resolver=None, cancel_check=None, audit_conn=None
    ):
        import os

        def resolve(p: str) -> str:
            if os.path.isabs(p):
                return p
            return os.path.join(workspace, p)

        ctx = SimpleNamespace(
            task_id=task_id,
            workspace_root=workspace,
            resolve=resolve,
            # Write-snapshot rollback is deferred to v2 (SPEC line 113): no-op.
            snapshot=lambda abspath: None,
            write_max_bytes=config.tools.write_max_bytes,
        )
        audit_log = AuditLog(audit_conn if audit_conn is not None else conn)
        return HarnessCore(
            llm=llm,
            dispatcher=dispatcher,
            audit=audit_log,
            config=config,
            ctx=ctx,
            final_verifier=_make_final_verifier(config, workspace),
            approval_resolver=approval_resolver,
            cancel_check=cancel_check,
            memory_store=memory_store,
            # Stable per-workspace project scope: same hash the task repo uses
            # (app_service._workspace_hash), so retrieved memory is per project.
            project_id=_workspace_hash(workspace),
        )

    return ApplicationService(
        db=conn,
        db_path=db_path,
        config=config,
        harness_factory=harness_factory,
        sync=sync,
    )
