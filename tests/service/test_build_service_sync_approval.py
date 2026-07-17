"""tests/service/test_build_service_sync_approval.py

Regression test for the Critical finding on Task 38: build_service had no way
to inject a sync_decision_fn, so ANY sync-mode REQUIRE_APPROVAL auto-rejected
(ApplicationService._build_sync_approval_resolver treats a missing decide_fn
as "not approved"). Since the shipped governance defaults route a root-level
write_file to REQUIRE_APPROVAL (write_allowlist_dirs=[src/, tests/]), every
write outside those dirs was unconditionally rejected in sync mode through the
REAL build_service path -- exactly the scenario the human-triggered
`make e2e-real-llm` harness exercises (it asks the LLM to write add.py/
test_add.py at the workspace root).

Zero network: MockLLM only (injected via monkeypatch on the module-level
MockLLM name that assembly.build_llm's "mock" branch calls), temp workspace,
sync=True. No real provider, no credential store needed.
"""
from __future__ import annotations

import pytest

from aegiscode.config.schema import AegisConfig, Llm, Workspace
from aegiscode.llm.mock import MockLLM

# One scripted action: write add.py at the workspace ROOT. write_allowlist_dirs
# defaults to ["src/", "tests/"], so this path is NOT allowlisted and hits
# default_decisions.write == REQUIRE_APPROVAL (the Critical's exact scenario).
_SCRIPTED_WRITE = [
    '{"tool":"write_file","arguments":{"path":"add.py","content":"def add(a,b): return a+b\\n"}}'
]


def _build_config(tmp_path):
    """Minimal config: mock provider, workspace/allowed_base = tmp_path."""
    return AegisConfig(
        workspace=Workspace(root=str(tmp_path), allowed_base=str(tmp_path)),
        llm=Llm(provider="mock", model="mock-model"),
    )


def _patch_scripted_mock_llm(monkeypatch):
    """Make build_llm's 'mock' branch (`MockLLM([])`) return a scripted MockLLM.

    build_llm only ever calls MockLLM([]) for provider=="mock" (no scripted
    responses in production). Patching the name assembly.py resolved at import
    time lets a real build_service() call carry our scripted action without
    touching any other production code path.
    """
    monkeypatch.setattr(
        "aegiscode.service.assembly.MockLLM",
        lambda _empty_list: MockLLM(list(_SCRIPTED_WRITE)),
    )


def test_sync_decision_fn_true_auto_approves_write(tmp_path, monkeypatch):
    """Test A: sync_decision_fn=lambda _id: True -> the write executes.

    This is the e2e harness's fix: a disposable sandbox auto-approver stands in
    for a human clicking "approve" on the toy task's writes.
    """
    from aegiscode.service.assembly import build_service

    _patch_scripted_mock_llm(monkeypatch)
    config = _build_config(tmp_path)
    db_path = str(tmp_path / "svc.db")

    service = build_service(
        config,
        credential_store=None,
        db_path=db_path,
        sync=True,
        sync_decision_fn=lambda approval_id: True,
    )
    task_id = service.create_task(workspace=str(tmp_path), description="write add.py")

    add_py = tmp_path / "add.py"
    assert add_py.is_file(), "auto-approved write must execute and create the file"

    approvals = service.list_approvals(task_id)
    assert any(a["state"] == "APPROVED" for a in approvals), approvals


def test_sync_decision_fn_default_none_rejects_write(tmp_path, monkeypatch):
    """Test B: default (no sync_decision_fn) -> the SAME write is REJECTED.

    Pins the exact production default: build_service's default posture (no
    injected decision fn) must keep failing closed for sync-mode approvals --
    this is deliberate, not the bug. The bug was that build_service offered NO
    way at all to inject an approver, so this was the only reachable outcome.
    """
    from aegiscode.service.assembly import build_service

    _patch_scripted_mock_llm(monkeypatch)
    config = _build_config(tmp_path)
    db_path = str(tmp_path / "svc.db")

    service = build_service(config, credential_store=None, db_path=db_path, sync=True)
    task_id = service.create_task(workspace=str(tmp_path), description="write add.py")

    add_py = tmp_path / "add.py"
    assert not add_py.is_file(), "default (no decision fn) must fail-closed reject the write"

    approvals = service.list_approvals(task_id)
    assert any(a["state"] == "REJECTED" for a in approvals), approvals
