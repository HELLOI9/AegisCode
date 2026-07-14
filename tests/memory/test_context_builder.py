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

def test_feedback_precedes_memories_in_order():
    msgs = build_context("SYS", "PROTO", "task", [], "FB-CONTENT",
                         [{"key": "k", "value": "MEM-CONTENT"}], budget_chars=100000)
    blob = [m["content"] for m in msgs]
    fb_idx = next(i for i, c in enumerate(blob) if "FB-CONTENT" in c)
    mem_idx = next(i for i, c in enumerate(blob) if "MEM-CONTENT" in c)
    assert fb_idx < mem_idx   # feedback (tier 4) before memories (tier 5)
