from aegiscode.llm.openai_adapter import OpenAIAdapter
from aegiscode.llm.anthropic_adapter import AnthropicAdapter

def fake_openai_post(url, headers, json):
    return {"choices":[{"message":{"content":"OK-OAI"}}]}

def fake_anthropic_post(url, headers, json):
    return {"content":[{"type":"text","text":"OK-ANT"}]}

def test_openai_extracts_text():
    a = OpenAIAdapter("gpt-4o","k", http_post=fake_openai_post)
    assert a.complete([{"role":"user","content":"hi"}]) == "OK-OAI"

def test_anthropic_extracts_text_and_splits_system():
    seen = {}
    def cap(url, headers, json): seen.update(json); return {"content":[{"type":"text","text":"OK-ANT"}]}
    a = AnthropicAdapter("claude-x","k", http_post=cap)
    out = a.complete([{"role":"system","content":"S"},{"role":"user","content":"U"}])
    assert out == "OK-ANT"
    assert seen["system"] == "S"                     # system pulled out of messages
    assert all(m["role"] != "system" for m in seen["messages"])
