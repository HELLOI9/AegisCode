import os
import yaml
from pydantic import ValidationError
from .schema import AegisConfig


class ConfigError(Exception): ...


# Exactly two env-var overrides are recognized (SPEC §11 M11):
_ENV_MAP = {
    "AEGIS_LLM_PROVIDER": ("llm", "provider"),
    "AEGIS_LLM_MODEL":    ("llm", "model"),
}


def _apply_env_overrides(raw: dict, env: dict | None) -> dict:
    """Merge the recognized env-var overrides into a raw config dict (in place).

    Single source of truth for the env map so EVERY config path — a YAML file
    or the no-file defaults — honors AEGIS_LLM_PROVIDER / AEGIS_LLM_MODEL
    identically. Without this shared helper the defaults path silently ignored
    the overrides, so `serve` in a clean container (no aegis.yaml) could not be
    switched to the mock provider via -e AEGIS_LLM_PROVIDER=mock.
    """
    src = os.environ if env is None else env
    for key, (section, field) in _ENV_MAP.items():
        if key in src:
            raw.setdefault(section, {})[field] = src[key]
    return raw


def _build(raw: dict) -> AegisConfig:
    try:
        return AegisConfig(**raw)
    except ValidationError as e:
        raise ConfigError(str(e)) from e


def load_config(path: str, env: dict | None = None) -> AegisConfig:
    try:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML: {e}") from e
    return _build(_apply_env_overrides(raw, env))


def load_defaults(env: dict | None = None) -> AegisConfig:
    """Build config from schema defaults, still applying env-var overrides.

    This is the no-config-file path (no aegis.yaml on disk). It must NOT bypass
    the env overrides — that bypass was the bug that made `serve` ignore
    AEGIS_LLM_PROVIDER=mock in a clean container.
    """
    return _build(_apply_env_overrides({}, env))
