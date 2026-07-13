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


def load_config(path: str, env: dict | None = None) -> AegisConfig:
    try:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML: {e}") from e
    src = os.environ if env is None else env
    for key, (section, field) in _ENV_MAP.items():
        if key in src:
            raw.setdefault(section, {})[field] = src[key]
    try:
        return AegisConfig(**raw)
    except ValidationError as e:
        raise ConfigError(str(e)) from e
