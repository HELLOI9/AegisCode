# tests/loop/test_memory_integration.py
"""Memory RETRIEVAL wired into the live loop (acceptance §一 closed loop).

These tests assert the read path: MemoryStore.retrieve() -> is_governance_usable
filter -> build_context, end to end, deterministically. The write path (agent
proposing memory during a run) is out of scope for this task.
"""
from __future__ import annotations

from types import SimpleNamespace

from aegiscode.audit.chain import AuditLog
from aegiscode.config.schema import AegisConfig, Workspace
from aegiscode.governance.factory import build_dispatcher
from aegiscode.llm.mock import MockLLM
from aegiscode.loop.harness import HarnessCore
from aegiscode.memory.store import MemoryStore
from aegiscode.persistence.db import open_db
from aegiscode.tools.finish_tool import FinishTool
from aegiscode.tools.registry import ToolRegistry


def _make_harness(tmp_path, *, memory_store=None, project_id=None, scripted=None):
    """Build a HarnessCore with a real dispatcher + MockLLM (records messages).

    MockLLM.received_messages[0] is the message list built for the first turn.
    """
    config = AegisConfig(workspace=Workspace(root=str(tmp_path)))
    reg = ToolRegistry()
    reg.register(FinishTool())
    dispatcher = build_dispatcher(config, reg)

    conn = open_db(str(tmp_path / "audit.db"))
    audit = AuditLog(conn)

    llm = MockLLM(scripted or ['{"tool":"finish","arguments":{}}'])

    ctx = SimpleNamespace(
        task_id="t1",
        workspace_root=str(tmp_path),
        resolve=lambda p: p,
        snapshot=lambda abspath: None,
        write_max_bytes=config.tools.write_max_bytes,
    )

    return HarnessCore(
        llm=llm,
        dispatcher=dispatcher,
        audit=audit,
        config=config,
        ctx=ctx,
        final_verifier=lambda: True,
        memory_store=memory_store,
        project_id=project_id,
    )


def _first_turn_text(llm) -> str:
    assert llm.received_messages, "LLM was never called"
    return "\n".join(m["content"] for m in llm.received_messages[0])


def test_retrieval_reaches_context(tmp_path):
    """A seeded project memory (source=user) appears in the LLM messages."""
    store = MemoryStore(open_db(str(tmp_path / "mem.db")))
    store.write("proj-A", "PROJECT_CONVENTION", "indent_style",
                "use 4-space indentation", ["style"], "user")

    h = _make_harness(tmp_path, memory_store=store, project_id="proj-A")
    h.run("do the task")

    text = _first_turn_text(h.llm)
    assert "indent_style" in text
    assert "use 4-space indentation" in text
    assert "MEMORY:" in text


def test_agent_memory_filtered_out(tmp_path):
    """Agent-sourced memory is NOT fed into context (is_governance_usable=False).

    SPEC §M10: source=agent memory is 仅提示、永不作治理依据 (never a governance
    basis); honoring the harness TODO, we filter it out before build_context.
    """
    store = MemoryStore(open_db(str(tmp_path / "mem.db")))
    store.write("proj-A", "PROJECT_CONVENTION", "confirmed_fact",
                "prod uses postgres", [], "user")
    store.write("proj-A", "DECISION", "agent_guess",
                "maybe switch to redis", [], "agent")

    h = _make_harness(tmp_path, memory_store=store, project_id="proj-A")
    h.run("do the task")

    text = _first_turn_text(h.llm)
    assert "confirmed_fact" in text          # user row present
    assert "prod uses postgres" in text
    assert "agent_guess" not in text          # agent row filtered
    assert "maybe switch to redis" not in text


def test_no_memory_backcompat(tmp_path):
    """HarnessCore without a memory_store behaves as before: empty MEMORY tier."""
    h = _make_harness(tmp_path, memory_store=None, project_id=None)
    h.run("do the task")

    text = _first_turn_text(h.llm)
    assert "MEMORY:" not in text


def test_determinism_same_seed_same_context(tmp_path):
    """Same seeded store -> identical retrieved memory content across runs."""
    def build_and_run(db_dir):
        store = MemoryStore(open_db(str(db_dir / "mem.db")))
        store.write("proj-A", "CODEBASE_FACT", "entrypoint",
                    "main is aegiscode/cli.py", [], "user")
        h = _make_harness(db_dir, memory_store=store, project_id="proj-A")
        h.run("do the task")
        return _first_turn_text(h.llm)

    d1 = tmp_path / "run1"
    d2 = tmp_path / "run2"
    d1.mkdir()
    d2.mkdir()
    t1 = build_and_run(d1)
    t2 = build_and_run(d2)
    assert "entrypoint" in t1 and "main is aegiscode/cli.py" in t1
    assert t1 == t2
