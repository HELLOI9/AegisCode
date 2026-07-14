"""Credential store: layered read order (keyring → .env → env), masked status."""

SERVICE, USER = "aegiscode", "llm_api_key"


class CredentialStore:
    def __init__(self, backend, allow_dotenv=False, env=None, dotenv_path=None):
        self.backend = backend
        self.allow_dotenv = allow_dotenv
        self.env = env or {}
        self.dotenv_path = dotenv_path

    def set_key(self, value):
        self.backend.set_password(SERVICE, USER, value)

    def clear(self):
        try:
            self.backend.delete_password(SERVICE, USER)
        except Exception:
            pass

    def get_key(self):
        # Layer 1: keyring backend (fail-safe)
        try:
            v = self.backend.get_password(SERVICE, USER)
        except Exception:
            v = None
        if v:
            return v
        # Layer 2: .env file (only when explicitly enabled)
        if self.allow_dotenv and self.dotenv_path:
            try:
                with open(self.dotenv_path) as f:
                    for line in f:
                        if line.startswith("OPENAI_API_KEY="):
                            return line.split("=", 1)[1].strip()
            except OSError:
                pass
        # Layer 3: environment dict
        return self.env.get("OPENAI_API_KEY")

    def status(self):
        v = self.get_key()
        if not v:
            return {"configured": False, "masked": None}
        # Mask: show up to first 3 chars + ellipsis + last 4 — NEVER the full key
        prefix = v[:3]
        suffix = v[-4:] if len(v) >= 4 else v
        masked = prefix + "…" + suffix
        return {"configured": True, "masked": masked}
