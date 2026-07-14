"""tests/test_cli.py — CLI surface (T29). All tests offline/deterministic.

Every credential test sets AEGIS_HOME to a tmp dir so the JSON-file backend is
used instead of the host OS keyring — hermetic and never touches the machine.
"""
from __future__ import annotations

import getpass

from aegiscode.cli import main
from aegiscode.config.loader import load_config


# --------------------------------------------------------------------------
# MANDATORY given tests
# --------------------------------------------------------------------------


def test_key_status_not_configured(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("AEGIS_HOME", str(tmp_path))
    main(["key", "status"])
    out = capsys.readouterr().out.lower()
    assert "not configured" in out or "configured: false" in out


def test_config_validates(tmp_path, capsys):
    (tmp_path / "aegis.yaml").write_text("limits:\n  max_steps: 25\n")
    rc = main(["config", "--path", str(tmp_path / "aegis.yaml")])
    assert rc == 0


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------


def test_init_writes_loadable_config(tmp_path):
    target = tmp_path / "aegis.yaml"
    rc = main(["init", "--path", str(target)])
    assert rc == 0
    assert target.exists()
    # The scaffold must round-trip through load_config without error.
    cfg = load_config(str(target))
    assert cfg.limits.max_steps > 0


def test_init_no_overwrite_without_force(tmp_path, capsys):
    target = tmp_path / "aegis.yaml"
    target.write_text("limits:\n  max_steps: 7\n")
    rc = main(["init", "--path", str(target)])
    assert rc != 0
    # Original content preserved.
    assert "max_steps: 7" in target.read_text()


def test_init_force_overwrites(tmp_path):
    target = tmp_path / "aegis.yaml"
    target.write_text("limits:\n  max_steps: 7\n")
    rc = main(["init", "--path", str(target), "--force"])
    assert rc == 0
    cfg = load_config(str(target))
    # Scaffold default differs from the 7 we planted.
    assert cfg.limits.max_steps != 7


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------


def test_config_invalid_yaml_returns_nonzero_no_raise(tmp_path, capsys):
    bad = tmp_path / "aegis.yaml"
    # Unknown top-level key -> ConfigError (extra=forbid), must NOT raise.
    bad.write_text("not_a_real_section: 1\n")
    rc = main(["config", "--path", str(bad)])
    assert rc != 0
    err = capsys.readouterr().err
    assert err  # error printed to stderr


def test_config_malformed_yaml_returns_nonzero(tmp_path, capsys):
    bad = tmp_path / "aegis.yaml"
    bad.write_text("limits: [unclosed\n")
    rc = main(["config", "--path", str(bad)])
    assert rc != 0


# --------------------------------------------------------------------------
# key set / status / clear
# --------------------------------------------------------------------------


def test_key_set_then_status_masked(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("AEGIS_HOME", str(tmp_path))
    fake_key = "sk-abc1234567890XYZ"
    monkeypatch.setattr(getpass, "getpass", lambda *a, **k: fake_key)

    rc = main(["key", "set"])
    assert rc == 0
    set_out = capsys.readouterr().out
    # The plaintext key must NEVER be echoed, not even by `set`.
    assert fake_key not in set_out

    rc = main(["key", "status"])
    assert rc == 0
    status_out = capsys.readouterr().out
    assert fake_key not in status_out  # never the full key
    assert "abc" in status_out or "…" in status_out  # masked shown


def test_key_clear_makes_status_unconfigured(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("AEGIS_HOME", str(tmp_path))
    monkeypatch.setattr(getpass, "getpass", lambda *a, **k: "sk-topsecret1234567890")
    main(["key", "set"])
    capsys.readouterr()

    rc = main(["key", "clear"])
    assert rc == 0
    capsys.readouterr()

    main(["key", "status"])
    out = capsys.readouterr().out.lower()
    assert "not configured" in out or "configured: false" in out


# --------------------------------------------------------------------------
# demo (zero-network governance interception)
# --------------------------------------------------------------------------


def test_demo_returns_zero_and_prints_pass(capsys):
    rc = main(["demo"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PASS" in out


# --------------------------------------------------------------------------
# run — mock provider, zero network. Uses sync execution so it terminates.
# --------------------------------------------------------------------------


def test_run_mock_provider_prints_task_id(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("AEGIS_HOME", str(tmp_path / "home"))
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = tmp_path / "aegis.yaml"
    cfg.write_text("llm:\n  provider: mock\n")

    rc = main(["run", "--workspace", str(ws), "--task", "do nothing",
               "--config", str(cfg)])
    # Mock LLM has an empty script -> harness terminates (LLM_ERROR); the CLI
    # must still create the task and exit cleanly (zero network touched).
    assert rc == 0
    out = capsys.readouterr().out
    assert "task" in out.lower()


def test_run_openai_no_key_friendly_error(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("AEGIS_HOME", str(tmp_path / "home"))
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = tmp_path / "aegis.yaml"
    cfg.write_text("llm:\n  provider: openai\n")

    rc = main(["run", "--workspace", str(ws), "--task", "x", "--config", str(cfg)])
    assert rc != 0
    err = (capsys.readouterr().err + capsys.readouterr().out).lower()
    assert "key" in err  # friendly "no API key configured" message


# --------------------------------------------------------------------------
# serve — never binds a socket; uvicorn.run is monkeypatched.
# --------------------------------------------------------------------------


def test_serve_binds_localhost_and_prints_notice(tmp_path, capsys, monkeypatch):
    import uvicorn
    monkeypatch.setenv("AEGIS_HOME", str(tmp_path / "home"))
    cfg = tmp_path / "aegis.yaml"
    cfg.write_text("llm:\n  provider: mock\n")

    captured = {}

    def fake_run(app, host=None, port=None, **kwargs):
        captured["host"] = host
        captured["port"] = port
        # Do NOT bind — return immediately.

    monkeypatch.setattr(uvicorn, "run", fake_run)

    rc = main(["serve", "--config", str(cfg)])
    assert rc == 0
    assert captured["host"] == "127.0.0.1"
    out = capsys.readouterr().out.lower()
    assert "localhost" in out or "127.0.0.1" in out


# --------------------------------------------------------------------------
# Console-script entry point: `main()` must work with NO args.
# Regression guard for the setuptools entry `aegiscode = aegiscode.cli:main`,
# which calls main() with zero arguments. A missing argv default made every
# real `aegiscode ...` invocation (incl. the Docker CMD `aegiscode serve`)
# crash with TypeError before this was fixed. All other tests pass argv
# explicitly, so this path was previously unguarded.
# --------------------------------------------------------------------------


def test_main_no_args_reads_sys_argv(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("AEGIS_HOME", str(tmp_path))
    # Simulate the console script: `aegiscode key status` with main() called
    # with no positional argv (setuptools convention).
    monkeypatch.setattr("sys.argv", ["aegiscode", "key", "status"])
    rc = main()  # must NOT raise TypeError
    assert rc == 0
    out = capsys.readouterr().out.lower()
    assert "not configured" in out or "configured: false" in out


# --------------------------------------------------------------------------
# _load_config env override with NO config file (clean-env / container path).
# Regression: `serve` in a container has no aegis.yaml, so _load_config must
# still honor AEGIS_LLM_PROVIDER=mock (else it defaults to openai and refuses
# to serve with no key — breaking MockLLM-mode serve, acceptance §五/§八).
# --------------------------------------------------------------------------


def test_load_config_applies_env_override_without_config_file(tmp_path, monkeypatch):
    from aegiscode.cli import _load_config

    # A working dir with NO aegis.yaml (the container/clean-env situation).
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AEGIS_LLM_PROVIDER", "mock")

    cfg = _load_config(None)

    assert cfg.llm.provider == "mock", (
        "AEGIS_LLM_PROVIDER must apply even when no aegis.yaml exists"
    )
