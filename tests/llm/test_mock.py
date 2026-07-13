import pytest
from aegiscode.llm.mock import MockLLM, MockExhaustedError

def test_returns_scripted_in_order():
    m = MockLLM(["a", "b"])
    assert m.complete([{"role":"user","content":"x"}]) == "a"
    assert m.complete([{"role":"user","content":"y"}]) == "b"

def test_records_received_messages():
    m = MockLLM(["a"])
    m.complete([{"role":"user","content":"hi"}])
    assert m.received_messages[0][0]["content"] == "hi"

def test_raises_when_exhausted():
    m = MockLLM([])
    with pytest.raises(MockExhaustedError):
        m.complete([])

def test_received_messages_not_aliased():
    m = MockLLM(["a"])
    msgs = [{"role": "user", "content": "hi"}]
    m.complete(msgs)
    msgs.append({"role": "user", "content": "MUTATED"})   # caller mutates after the call
    assert m.received_messages[0] == [{"role": "user", "content": "hi"}]  # recording unchanged
