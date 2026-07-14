# tests/credentials/test_store.py
from aegiscode.credentials.store import CredentialStore

class FakeBackend:
    def __init__(self): self.v = None
    def set_password(self, s, u, v): self.v = v
    def get_password(self, s, u): return self.v
    def delete_password(self, s, u): self.v = None

def test_status_masks_never_plaintext():
    b = FakeBackend(); cs = CredentialStore(b); cs.set_key("sk-abcdef1234567890")
    st = cs.status()
    assert st["configured"] is True
    assert "sk-abcdef1234567890" not in str(st) and st["masked"].endswith("7890")

def test_dotenv_disabled_by_default(tmp_path):
    p = tmp_path/".env"; p.write_text("OPENAI_API_KEY=sk-fromdotenv")
    cs = CredentialStore(FakeBackend(), allow_dotenv=False, dotenv_path=str(p))
    assert cs.get_key() is None

def test_env_fallback():
    cs = CredentialStore(FakeBackend(), env={"OPENAI_API_KEY":"sk-env"})
    assert cs.get_key() == "sk-env"

def test_clear():
    b = FakeBackend(); cs = CredentialStore(b); cs.set_key("x"); cs.clear()
    assert cs.status()["configured"] is False

# --- additional robustness tests ---

def test_keyring_preferred_over_env():
    b = FakeBackend(); b.v = "sk-fromkeyring"
    cs = CredentialStore(b, env={"OPENAI_API_KEY": "sk-fromenv"})
    assert cs.get_key() == "sk-fromkeyring"

def test_allow_dotenv_reads_dotenv(tmp_path):
    p = tmp_path / ".env"; p.write_text("OPENAI_API_KEY=sk-fromdotenv\n")
    cs = CredentialStore(FakeBackend(), allow_dotenv=True, dotenv_path=str(p))
    assert cs.get_key() == "sk-fromdotenv"

def test_get_key_none_when_nothing_configured():
    cs = CredentialStore(FakeBackend())
    assert cs.get_key() is None

def test_masked_format_short_key():
    b = FakeBackend(); cs = CredentialStore(b); cs.set_key("sk-1234")
    st = cs.status()
    assert st["configured"] is True
    assert "sk-1234" not in str(st)
    assert st["masked"].endswith("1234")

def test_clear_swallows_backend_errors():
    class ErrorBackend(FakeBackend):
        def delete_password(self, s, u): raise RuntimeError("keyring locked")
    cs = CredentialStore(ErrorBackend())
    cs.set_key("val")
    cs.clear()  # must not raise

def test_get_key_swallows_backend_errors():
    class ErrorBackend(FakeBackend):
        def get_password(self, s, u): raise RuntimeError("keyring locked")
    cs = CredentialStore(ErrorBackend(), env={"OPENAI_API_KEY": "sk-fallback"})
    assert cs.get_key() == "sk-fallback"
