"""tests/helpers.py — shared test factory for HarnessCore integration tests."""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from typing import Any

from aegiscode.audit.chain import AuditLog
from aegiscode.config.schema import AegisConfig, Limits, Governance, Workspace
from aegiscode.governance.factory import build_dispatcher, build_path_config
from aegiscode.llm.mock import MockLLM
from aegiscode.tools.file_tools import WriteFileTool, ReadFileTool, ListFilesTool, SearchTextTool
from aegiscode.tools.finish_tool import FinishTool
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.result import ToolResult


class SpyCommandTool:
    """Replaces RunCommandTool in tests — never actually executes, just records."""
    name = "run_command"

    def __init__(self, spy):
        self._spy = spy

    def run(self, arguments, ctx):
        self._spy.command_executions += 1
        return ToolResult(
            tool=self.name,
            status="success",
            summary=f"spy: {arguments.get('command', '')}",
        )


class SpyRunTestsTool:
    """Replaces RunTestsTool — returns failure on first call if fail_first_test, then success."""
    name = "run_tests"

    def __init__(self, spy, fail_first_test: bool):
        self._spy = spy
        self._fail_first = fail_first_test
        self._call_count = 0

    def run(self, arguments, ctx):
        self._call_count += 1
        self._spy.run_tests_executions += 1
        if self._fail_first and self._call_count == 1:
            return ToolResult(
                tool=self.name,
                status="failure",
                summary="tests exit 1",
                detail_for_llm="TEST_FAILURE: 1 test failed\nAssertionError: expected 1 got 0",
                exit_code=1,
            )
        return ToolResult(
            tool=self.name,
            status="success",
            summary="tests exit 0",
            detail_for_llm="1 passed",
            exit_code=0,
        )


class SpyAuditLog:
    """Wraps AuditLog and records all events for test assertions."""

    def __init__(self, real_audit: AuditLog, spy):
        self._real = real_audit
        self._spy = spy

    def append(self, task_id, step_index, event_type, payload: dict) -> str:
        h = self._real.append(task_id, step_index, event_type, payload)
        self._spy.audit_events.append({
            "task_id": task_id,
            "step_index": step_index,
            "event_type": getattr(event_type, "value", str(event_type)),
            **payload,
        })
        return h


class Spy:
    """Records observable side-effects for test assertions."""

    def __init__(self):
        self.command_executions: int = 0
        self.run_tests_executions: int = 0
        self.audit_events: list[dict] = []
        self._messages_by_round: dict[int, list[str]] = {}
        self._actions_by_round: dict[int, str] = {}
        self._round: int = 0  # 1-indexed to match brief's "round 3"

    def record_messages(self, messages: list[dict], round_num: int) -> None:
        self._messages_by_round[round_num] = [m["content"] for m in messages]

    def record_action(self, action_str: str, round_num: int) -> None:
        self._actions_by_round[round_num] = action_str

    def messages_at_round(self, round_num: int) -> list[str]:
        return self._messages_by_round.get(round_num, [])

    def action_at(self, round_num: int) -> str:
        return self._actions_by_round.get(round_num, "")


class SpyLLM:
    """Wraps MockLLM and records messages/actions per round for test assertions."""

    def __init__(self, mock_llm: MockLLM, spy: Spy):
        self._mock = mock_llm
        self._spy = spy
        self._call_count = 0

    def complete(self, messages: list[dict]) -> str:
        self._call_count += 1
        round_num = self._call_count
        self._spy.record_messages(messages, round_num)
        text = self._mock.complete(messages)
        # Record the action text (raw LLM output)
        self._spy.record_action(text, round_num)
        return text


def _build_registry(spy: Spy, fail_first_test: bool) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(WriteFileTool())
    reg.register(ReadFileTool())
    reg.register(ListFilesTool())
    reg.register(SearchTextTool())
    reg.register(SpyCommandTool(spy))
    reg.register(SpyRunTestsTool(spy, fail_first_test))
    reg.register(FinishTool())
    return reg


def _build_ctx(tmp_path, config: AegisConfig) -> SimpleNamespace:
    """Build a ctx namespace compatible with all tools and harness internals."""
    workspace = str(tmp_path)

    def resolve(p: str) -> str:
        import os
        if os.path.isabs(p):
            return p
        return os.path.join(workspace, p)

    def snapshot(abspath: str) -> None:
        pass  # no-op for tests

    return SimpleNamespace(
        task_id="test",
        workspace_root=workspace,
        resolve=resolve,
        snapshot=snapshot,
        write_max_bytes=config.tools.write_max_bytes,
    )


def make_harness(tmp_path, scripted: list[str], final_ok: bool = True,
                 fail_first_test: bool = False):
    """
    Build a HarnessCore wired with real governance components and a MockLLM.

    Returns (harness, spy) where spy records:
    - spy.command_executions: int
    - spy.audit_events: list[dict]
    - spy.messages_at_round(n): list[str]  (1-indexed)
    - spy.action_at(n): str               (1-indexed)
    """
    from aegiscode.loop.harness import HarnessCore

    spy = Spy()

    # Config: write allowlist includes src/ so write_file to src/m.py is allowed
    config = AegisConfig(
        workspace=Workspace(root=str(tmp_path)),
        limits=Limits(
            max_steps=20,
            max_consecutive_failures=5,
            no_progress_repeat_limit=3,
            action_retry_limit=3,
        ),
    )

    # Registry with spy tools
    registry = _build_registry(spy, fail_first_test)

    # Dispatcher via factory (real governance)
    dispatcher = build_dispatcher(config, registry)

    # AuditLog on tmp_path db
    from aegiscode.persistence.db import open_db
    conn = open_db(str(tmp_path / "audit.db"))
    real_audit = AuditLog(conn)
    spy_audit = SpyAuditLog(real_audit, spy)

    # LLM: MockLLM wrapped in SpyLLM
    mock_llm = MockLLM(scripted)
    spy_llm = SpyLLM(mock_llm, spy)

    # Context
    ctx = _build_ctx(tmp_path, config)

    # final_verifier callable
    def final_verifier() -> bool:
        return final_ok

    harness = HarnessCore(
        llm=spy_llm,
        dispatcher=dispatcher,
        audit=spy_audit,
        config=config,
        ctx=ctx,
        final_verifier=final_verifier,
    )

    return harness, spy
