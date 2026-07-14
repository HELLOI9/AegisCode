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


def test_scan_gate_fails_on_planted_key_through_full_path(tmp_path, monkeypatch):
    """Exercise the REAL gate path (rglob walk + allowlist filter + exit code),
    not just the underlying regex. Point REPO_ROOT at a temp tree with a planted
    key under a shipped dir and assert main() returns 1 and names the file.

    This is the anti-theater proof the committed suite must carry: it fails if
    shipped_py_files()/remaining_findings()/main() were broken, whereas a bare
    scan_text() assertion would not.
    """
    mod = _load_scan_module()
    (tmp_path / "aegiscode").mkdir()
    leak = tmp_path / "aegiscode" / "_planted_leak.py"
    leak.write_text("SECRET_KEY = 'sk-abcdef1234567890abcdef1234567890'\n")
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    remaining = mod.remaining_findings()
    assert remaining, "gate must detect the planted key on the shipped surface"
    assert any("_planted_leak.py" in str(f.path) for f in remaining)
    assert mod.main([]) == 1


def test_scan_gate_allowlist_suppresses_only_pinned_line(tmp_path, monkeypatch):
    """The allowlist must be line-pinned: a matching finding on the exact
    (path_suffix, line_no) is suppressed, but the SAME pattern on any other
    line is NOT — so the allowlist can't silently hide a real leak elsewhere.
    """
    mod = _load_scan_module()
    pkg = tmp_path / "aegiscode" / "service"
    pkg.mkdir(parents=True)
    # Line 1 = a benign identifier-triggered FP we allowlist; line 2 = real key.
    (pkg / "assembly.py").write_text(
        "key = credential_store.get_key()\n"
        "SECRET_KEY = 'sk-abcdef1234567890abcdef1234567890'\n"
    )
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "ALLOWLIST", [("aegiscode/service/assembly.py", 1)])

    remaining = mod.remaining_findings()
    # The line-1 FP is suppressed; the line-2 real key must survive.
    assert remaining, "real key on a non-allowlisted line must not be suppressed"
    assert all(f.line_no != 1 for f in remaining)
    assert any(f.line_no == 2 for f in remaining)


def test_scan_main_returns_zero_on_clean_tree():
    mod = _load_scan_module()
    assert mod.main([]) == 0
