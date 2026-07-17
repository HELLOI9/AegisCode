"""Human-triggered real-LLM end-to-end test (SPEC Appendix B.7).

NOT part of `make test` / CI. Uses a fresh temp workspace, a REAL provider from
config, and the real CLI path (build_service → HarnessCore). Proves the harness
(not hardcoded source) creates add.py/test_add.py and that COMPLETED depends on
pytest passing. May incur API cost. Output is redacted (no secret).
"""
from __future__ import annotations
import os, shlex, subprocess, sys, tempfile

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
    h = service._harness_factory(
        task_id="probe",
        workspace=tempfile.mkdtemp(),
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
    service = build_service(config, store, db_path, sync=True)
    provider_name = type(service_llm(service)).__name__
    task_id = service.create_task(workspace=workspace, description=TASK)
    row = service.get_task(task_id)
    completed = row.get("state") == "COMPLETED"
    # Independent pytest re-run over the harness output (does NOT modify files).
    p = subprocess.run(
        shlex.split("python -m pytest -q"), cwd=workspace,
        capture_output=True, text=True,
    )
    return provider_name, completed, p.returncode == 0

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
    provider_name, completed, pytest_passed = run_e2e(config, store, workspace)
    checks = verify(workspace, provider_name, completed, pytest_passed)
    print(f"workspace={workspace}")
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    ok = all(checks.values())
    print("E2E RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
