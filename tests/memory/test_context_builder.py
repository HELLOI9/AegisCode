# tests/memory/test_context_builder.py
from aegiscode.memory.context_builder import build_context, summarize_step

def test_summarize_step_is_deterministic_and_lossy():
    step = {"tool":"write_file","governance_decision":"ALLOW","feedback_category":"TEST_FAILURE",
            "detail":"x"*5000}
    s = summarize_step(step)
    assert "write_file" in s and "TEST_FAILURE" in s and "x"*5000 not in s
    assert summarize_step(step) == s               # deterministic

def test_budget_triggers_summarization():
    steps = [{"tool":"write_file","governance_decision":"ALLOW",
              "feedback_category":None,"detail":"y"*3000} for _ in range(10)]
    msgs = build_context("SYS","PROTO","task", steps, "fb", [], budget_chars=4000)
    assert sum(len(m["content"]) for m in msgs) <= 4000 * 1.2   # bounded
    assert any(m["role"]=="system" for m in msgs)               # system never dropped
