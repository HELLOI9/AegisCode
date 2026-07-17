import aegiscode.llm.openai_adapter as oa
from aegiscode.llm.openai_adapter import OpenAIAdapter, _real_post, HTTP_TIMEOUT_SEC
from aegiscode.llm.anthropic_adapter import AnthropicAdapter


def test_real_post_passes_timeout_to_urlopen(monkeypatch):
    # A hung connection must not block forever: _real_post must pass an explicit
    # bounded timeout= to urllib urlopen. Monkeypatch urlopen — NO real network.
    seen = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"ok": true}'

    def fake_urlopen(req, *args, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        return _Resp()

    monkeypatch.setattr(oa.urllib.request, "urlopen", fake_urlopen)
    _real_post("https://x/y", {}, {"a": 1})
    assert seen["timeout"] == HTTP_TIMEOUT_SEC
    assert isinstance(HTTP_TIMEOUT_SEC, (int, float)) and HTTP_TIMEOUT_SEC > 0

def fake_openai_post(url, headers, json):
    return {"choices":[{"message":{"content":"OK-OAI"}}]}

def test_openai_extracts_text():
    a = OpenAIAdapter("gpt-4o","k", http_post=fake_openai_post)
    assert a.complete([{"role":"user","content":"hi"}]) == "OK-OAI"

def test_openai_uses_custom_base_url():
    seen = {}
    def cap(url, headers, json):
        seen["url"] = url
        return {"choices":[{"message":{"content":"ok"}}]}
    a = OpenAIAdapter("gpt-4o", "k", base_url="https://proxy.example/v1", http_post=cap)
    a.complete([{"role":"user","content":"hi"}])
    assert seen["url"].startswith("https://proxy.example/v1")
    assert "chat/completions" in seen["url"]

def test_anthropic_extracts_text_and_splits_system():
    seen = {}
    def cap(url, headers, json): seen.update(json); return {"content":[{"type":"text","text":"OK-ANT"}]}
    a = AnthropicAdapter("claude-x","k", http_post=cap)
    out = a.complete([{"role":"system","content":"S"},{"role":"user","content":"U"}])
    assert out == "OK-ANT"
    assert seen["system"] == "S"                     # system pulled out of messages
    assert all(m["role"] != "system" for m in seen["messages"])

def test_anthropic_uses_custom_base_url():
    seen = {}
    def cap(url, headers, json):
        seen["url"] = url
        return {"content":[{"type":"text","text":"ok"}]}
    a = AnthropicAdapter("claude-x", "k", base_url="https://proxy.example", http_post=cap)
    a.complete([{"role":"user","content":"hi"}])
    assert seen["url"] == "https://proxy.example/v1/messages"

def test_anthropic_default_base_url():
    seen = {}
    def cap(url, headers, json):
        seen["url"] = url
        return {"content":[{"type":"text","text":"ok"}]}
    a = AnthropicAdapter("claude-x", "k", http_post=cap)
    a.complete([{"role":"user","content":"hi"}])
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
