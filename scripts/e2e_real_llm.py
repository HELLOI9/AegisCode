"""Human-triggered real-LLM end-to-end test (SPEC Appendix B.7).

NOT part of `make test` / CI. Uses a fresh temp workspace, a REAL provider from
config, and the real CLI path (build_service → HarnessCore). Proves the harness
(not hardcoded source) creates add.py/test_add.py and that COMPLETED depends on
pytest passing. May incur API cost. Output is redacted (no secret).
"""
from __future__ import annotations
import json, os, shlex, subprocess, sys, tempfile

TASK = (
    "In the current workspace create add.py and test_add.py. "
    "add.py must define add(a, b) returning the sum of two positive integers. "
    "test_add.py must use pytest and assert add(1,2)==3, add(10,20)==30, "
    "add(123,456)==579, add(7,8)==15. Do not access files outside the workspace, "
    "do not use the network, do not create unrelated files. Run pytest -q and only "
    "finish once all tests pass."
)

def verify(workspace, provider_name, completed, pytest_passed):
    """Return a dict of named boolean checks. All True => e2e PASS."""
    add_py = os.path.join(workspace, "add.py")
    test_py = os.path.join(workspace, "test_add.py")
    checks = {
        "real_provider": provider_name != "MockLLM",
        "add_py_exists": os.path.isfile(add_py),
        "test_add_py_exists": os.path.isfile(test_py),
        "completed": bool(completed),
        "pytest_passed": bool(pytest_passed),
    }
    return checks

def service_llm(service):
    # Reach the concrete llm the service's harness_factory bound (for provider proof).
    # Uses a throwaway probe workspace that must not leak on disk after the check.
    with tempfile.TemporaryDirectory() as probe_workspace:
        h = service._harness_factory(
            task_id="probe",
            workspace=probe_workspace,
            approval_resolver=None,
            cancel_check=None,
            audit_conn=None,
        )
        return h.llm

def run_e2e(config, store, workspace):
    from aegiscode.service.assembly import build_service

    db_path = os.path.join(workspace, ".aegis.db")
    if config.workspace.allowed_base is None:
        config.workspace.allowed_base = workspace
    # sync_decision_fn stands in for a human clicking "approve" on THIS toy
    # task's writes: the task instructs the LLM to write add.py/test_add.py at
    # the workspace root, which is outside the shipped write_allowlist_dirs
    # (src/, tests/) and so hits REQUIRE_APPROVAL. Auto-approving here only
    # authorizes those benign writes — dangerous commands (git push, rm -rf,
    # python -c, etc.) are governed as DENY, not REQUIRE_APPROVAL, so this
    # cannot be used to bypass a DENY. Without this, sync-mode approvals with
    # no decision fn auto-reject (fail closed), so the run would never be able
    # to create the files and the e2e would fail on every run regardless of
    # provider. This exercises the full HITL path end to end: write ->
    # REQUIRE_APPROVAL -> approved -> executed.
    service = build_service(
        config, store, db_path, sync=True, sync_decision_fn=lambda approval_id: True
    )
    provider_name = type(service_llm(service)).__name__
    task_id = service.create_task(workspace=workspace, description=TASK)
    row = service.get_task(task_id)
    completed = row.get("state") == "COMPLETED"
    # Independent pytest re-run over the harness output (does NOT modify files).
    p = subprocess.run(
        shlex.split("python -m pytest -q"), cwd=workspace,
        capture_output=True, text=True,
    )
    return service, task_id, provider_name, completed, p.returncode == 0


def governance_evidence(service, task_id):
    """Summarize audit events proving actions passed parse -> governance -> dispatch.

    Returns a dict of redacted counts/booleans only (no secrets, no raw content).
    """
    import json as _json

    from aegiscode.audit.events import EventType

    events = service.get_events(task_id, since=0)
    governance_decisions = 0
    approval_approved = False
    write_file_executed = 0
    for ev in events:
        et = ev.get("event_type")
        payload = ev.get("payload_json") or {}
        if isinstance(payload, str):
            payload = _json.loads(payload)
        if et == str(EventType.GOVERNANCE_DECISION):
            governance_decisions += 1
        elif et == str(EventType.APPROVAL_DECIDED):
            if payload.get("state") == "APPROVED":
                approval_approved = True
        elif et == str(EventType.TOOL_EXECUTED):
            if payload.get("tool") == "write_file":
                write_file_executed += 1
    return {
        "governance_decision_events": governance_decisions,
        "approval_approved": approval_approved,
        "write_file_tool_executed_events": write_file_executed,
    }

def _payload(ev):
    raw = ev.get("payload_json") or ev.get("payload") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {"_raw": str(raw)}

def format_trace(events):
    """Render the audit event stream as a readable per-step trace (SPEC B.9).

    Consumes the dict shape returned by `service.get_events(task_id, since=0)`:
    each row has `step_index`, `event_type` (the "EventType.X" string form),
    and `payload_json` (a JSON string). Purely offline/deterministic — never
    touches a real provider or the network.
    """
    lines = []
    for ev in events:
        et = str(ev.get("event_type", "")).replace("EventType.", "")
        si = ev.get("step_index", "?")
        p = _payload(ev)
        if et == "ACTION_PROPOSED":
            args = p.get("arguments", {})
            summary = args.get("path") or args.get("command") or args.get("query") or ""
            lines.append(f"  step{si} ACTION      {p.get('tool', '?')}  {summary}")
        elif et == "GOVERNANCE_DECISION":
            lines.append(f"  step{si} GOVERNANCE  {p.get('decision', '?')} "
                         f"[{p.get('rule', '')}] {p.get('reason', '')}")
        elif et == "APPROVAL_DECIDED":
            lines.append(f"  step{si} APPROVAL    {p.get('state', '?')}")
        elif et == "TOOL_EXECUTED":
            lines.append(f"  step{si} TOOL        {p.get('tool', '?')} -> {p.get('status', '?')}")
        elif et == "FEEDBACK":
            lines.append(f"  step{si} FEEDBACK    {p.get('category', '?')} {p.get('detail', '')}")
        elif et == "TERMINATION":
            lines.append(f"  step{si} TERMINATION reason={p.get('reason', '?')}")
    return "\n".join(lines)

def print_generated_files(workspace):
    """Print add.py/test_add.py contents from the e2e workspace (redacted-safe:
    these are the harness's own generated output, not credentials)."""
    for fn in ("add.py", "test_add.py"):
        fp = os.path.join(workspace, fn)
        print(f"\n----- {fn} -----")
        if os.path.isfile(fp):
            with open(fp, encoding="utf-8") as fh:
                print(fh.read().rstrip())
        else:
            print("(not created)")

def main():
    from aegiscode.config.loader import load_config
    from aegiscode.credentials.backend import build_credential_store

    cfg_path = os.environ.get("AEGIS_CONFIG", "aegis.yaml")
    config = load_config(cfg_path)
    if config.llm.provider == "mock":
        print("REFUSING: llm.provider is 'mock'. Set a real provider + key.", file=sys.stderr)
        return 2
    store = build_credential_store()
    workspace = tempfile.mkdtemp(prefix="aegis-e2e-")
    print(f"provider={config.llm.provider} model={config.llm.model} "
          f"credential={'configured' if store.status()['configured'] else 'MISSING'}")
    service, task_id, provider_name, completed, pytest_passed = run_e2e(config, store, workspace)
    checks = verify(workspace, provider_name, completed, pytest_passed)
    events = service.get_events(task_id, since=0)
    print("\n===== 执行轨迹 (trace) =====")
    print(format_trace(events))
    print("\n===== 生成文件 =====")
    print_generated_files(workspace)
    print("\n===== 验收摘要 =====")
    print(f"workspace={workspace}")
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    # Governance evidence (redacted): proof the run actually went through
    # parse -> governance -> dispatch, not just that files landed on disk.
    evidence = governance_evidence(service, task_id)
    print(f"governance_decision_events={evidence['governance_decision_events']}")
    print(f"approval_approved={evidence['approval_approved']}")
    print(f"write_file_tool_executed_events={evidence['write_file_tool_executed_events']}")
    ok = all(checks.values())
    print("E2E RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
