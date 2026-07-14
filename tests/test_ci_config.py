"""Task 32: CI pipeline config + deterministic secret-scan gate.

Asserts the PLAN-mandated GitLab CI shape, the GitHub Actions mirror that
makes CI actually run on the GitHub-hosted repo, and that the self-written
secret-scan gate (§A.4C spirit: deterministic, unit-testable) is neither
broken nor vacuous.
"""
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(rel):
    return yaml.safe_load((REPO_ROOT / rel).read_text())


def _load_scan_module():
    path = REPO_ROOT / "scripts" / "ci_secret_scan.py"
    spec = importlib.util.spec_from_file_location("ci_secret_scan", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_gitlab_ci_has_unit_test_job_running_make_test():
    ci = _load_yaml(".gitlab-ci.yml")
    # PLAN-mandated: signed SPEC names the job `unit-test` and it runs `make test`.
    assert "unit-test" in ci
    assert "make test" in str(ci["unit-test"])


def test_gitlab_ci_has_security_and_build_jobs():
    ci = _load_yaml(".gitlab-ci.yml")
    assert "secret-scan" in ci
    assert "docker-build" in ci
    assert ci.get("stages") == ["test", "security", "build"]


def test_github_actions_mirror_exists_and_runs_make_test():
    gh = _load_yaml(".github/workflows/ci.yml")
    jobs = gh["jobs"]
    assert "unit-test" in jobs
    assert "secret-scan" in jobs
    assert "docker-build" in jobs
    assert "make test" in str(gh)


def test_scan_gate_clean_on_real_tree():
    # Proves the shipped surface + allowlist are clean on the current tree.
    mod = _load_scan_module()
    assert mod.remaining_findings() == []


def test_scan_gate_is_not_vacuous():
    # Proves the underlying mechanism still detects a planted key.
    mod = _load_scan_module()
    findings = mod.scan_text("x='sk-abcdef1234567890abcdef1234567890'")
    assert findings


def test_scan_main_returns_zero_on_clean_tree():
    mod = _load_scan_module()
    assert mod.main([]) == 0
