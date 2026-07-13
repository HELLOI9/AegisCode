import pytest
from aegiscode.config.loader import load_config, ConfigError

def test_loads_defaults_and_overrides(tmp_path):
    (tmp_path / "aegis.yaml").write_text(
        "workspace:\n  root: /workspace\n"
        "limits:\n  max_steps: 25\n  max_consecutive_failures: 5\n  no_progress_repeat_limit: 3\n"
        "llm:\n  provider: openai\n  model: gpt-4o\n"
    )
    cfg = load_config(str(tmp_path / "aegis.yaml"), env={})
    assert cfg.limits.max_steps == 25
    assert cfg.governance.default_decisions.command == "DENY"

def test_unknown_top_level_field_raises(tmp_path):
    (tmp_path / "aegis.yaml").write_text("bogus_top_field: 1\n")
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "aegis.yaml"), env={})

def test_unknown_nested_field_raises(tmp_path):
    (tmp_path / "aegis.yaml").write_text("governance:\n  totally_made_up: true\n")
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "aegis.yaml"), env={})

def test_bad_decision_tier_raises(tmp_path):
    (tmp_path / "aegis.yaml").write_text(
        "governance:\n  default_decisions:\n    command: NONSENSE_TIER\n"
    )
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "aegis.yaml"), env={})

def test_command_rules_flat_shape(tmp_path):
    (tmp_path / "aegis.yaml").write_text(
        "governance:\n  command_rules:\n"
        "    - {argv0: pip, args_contain: [install], decision: REQUIRE_APPROVAL}\n"
    )
    cfg = load_config(str(tmp_path / "aegis.yaml"), env={})
    assert cfg.governance.command_rules[0].argv0 == "pip"
    assert cfg.governance.command_rules[0].decision == "REQUIRE_APPROVAL"

def test_command_rules_reject_nested_match(tmp_path):
    (tmp_path / "aegis.yaml").write_text(
        "governance:\n  command_rules:\n"
        "    - {match: {argv0: git, args_contain: [push]}, decision: DENY}\n"
    )
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "aegis.yaml"), env={})

def test_type_error_raises(tmp_path):
    (tmp_path / "aegis.yaml").write_text("limits:\n  max_steps: not_an_int\n")
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "aegis.yaml"), env={})

def test_env_overrides_provider_and_model(tmp_path):
    (tmp_path / "aegis.yaml").write_text("llm:\n  provider: openai\n  model: gpt-4o\n")
    cfg = load_config(str(tmp_path / "aegis.yaml"),
                      env={"AEGIS_LLM_PROVIDER": "anthropic", "AEGIS_LLM_MODEL": "claude-x"})
    assert cfg.llm.provider == "anthropic" and cfg.llm.model == "claude-x"

def test_env_none_reads_os_environ(tmp_path, monkeypatch):
    # env=None must fall back to os.environ (SPEC §11 M11); guard the default branch.
    (tmp_path / "aegis.yaml").write_text("llm:\n  provider: openai\n  model: gpt-4o\n")
    monkeypatch.setenv("AEGIS_LLM_MODEL", "claude-from-os-env")
    cfg = load_config(str(tmp_path / "aegis.yaml"))   # env omitted → None → os.environ
    assert cfg.llm.model == "claude-from-os-env"

def test_default_command_rules_pip_install_require_approval():
    from aegiscode.config.schema import Governance, Decision
    rules = Governance().command_rules
    pip_rule = next(r for r in rules if r.argv0 == "pip" and "install" in r.args_contain)
    assert pip_rule.decision == Decision.REQUIRE_APPROVAL
