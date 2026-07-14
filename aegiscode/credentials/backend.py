"""Credential backend factory — keyring with a JSON-file fallback.

A backend exposes get_password / set_password / delete_password(service, user)
so it plugs directly into CredentialStore(backend=...).

Selection (build_credential_store):
  * AEGIS_HOME set   -> JSON-file backend at $AEGIS_HOME/credentials.json (0600).
                        Hermetic for tests AND the Docker / keyring-unavailable
                        fallback (SPEC: "keyring 不可用自动降级").
  * otherwise        -> real keyring backend; if keyring import or backend access
                        raises, fall back to a JSON-file backend under ~/.aegiscode.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from aegiscode.credentials.store import CredentialStore


class JsonFileBackend:
    """File-backed credential backend. Stores {"service/user": value} as JSON.

    The file is created with mode 0600 so the plaintext key is not world-readable.
    """

    def __init__(self, path: str):
        self.path = path

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, data: dict) -> None:
        d = os.path.dirname(self.path) or "."
        os.makedirs(d, exist_ok=True)
        # Write then tighten perms to 0600 (owner read/write only).
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _key(service: str, user: str) -> str:
        return f"{service}/{user}"

    def get_password(self, service: str, user: str):
        return self._load().get(self._key(service, user))

    def set_password(self, service: str, user: str, value: str) -> None:
        data = self._load()
        data[self._key(service, user)] = value
        self._save(data)

    def delete_password(self, service: str, user: str) -> None:
        data = self._load()
        data.pop(self._key(service, user), None)
        self._save(data)


def _keyring_backend():
    """Return the real keyring module (it exposes the 3 password methods).

    Raises if keyring is unavailable or has no usable backend, so the caller
    can fall back to the JSON-file backend.
    """
    import keyring

    # Touch the backend so a "no usable keyring" install fails here (not later).
    keyring.get_keyring()
    return keyring


def build_credential_store(env=None) -> CredentialStore:
    """Build a CredentialStore with the appropriate backend.

    Parameters
    ----------
    env : dict | None
        Environment mapping (defaults to os.environ). When it contains
        AEGIS_HOME, the JSON-file backend under that dir is used unconditionally.
    """
    src = os.environ if env is None else env
    aegis_home = src.get("AEGIS_HOME")

    if aegis_home:
        path = str(Path(aegis_home) / "credentials.json")
        return CredentialStore(backend=JsonFileBackend(path))

    try:
        backend = _keyring_backend()
    except Exception:  # noqa: BLE001 — any keyring failure -> file fallback
        default_home = Path.home() / ".aegiscode"
        backend = JsonFileBackend(str(default_home / "credentials.json"))

    return CredentialStore(backend=backend)
