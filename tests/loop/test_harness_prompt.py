from types import SimpleNamespace
from aegiscode.config.schema import AegisConfig
from aegiscode.loop.harness import HarnessCore
from aegiscode.llm.mock import MockLLM
from aegiscode.prompt.builder import PromptBuilder
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.finish_tool import FinishTool

class _Audit:
    def append(self, *a, **k): pass

def _harness(prompt_builder):
    cfg = AegisConfig()
    llm = MockLLM(['{"tool":"finish","arguments":{}}'])
    ctx = SimpleNamespace(task_id="t1", workspace_root="/tmp")
    return HarnessCore(
        llm=llm, dispatcher=None, audit=_Audit(), config=cfg, ctx=ctx,
        final_verifier=lambda: True, prompt_builder=prompt_builder,
    ), llm

def test_build_injects_prompt_when_builder_present():
    reg = ToolRegistry(); reg.register(FinishTool())
    pb = PromptBuilder(AegisConfig(), reg)
    h, llm = _harness(pb)
    msgs = h._build("do the thing", recent_steps=[], last_feedback="")
    system = "\n".join(m["content"] for m in msgs if m["role"] == "system")
    assert "AegisCode" in system            # system prompt present
    assert "finish" in system               # tool protocol present
    assert any("do the thing" in m["content"] for m in msgs)

def test_build_empty_prompt_when_no_builder_backcompat():
    h, _ = _harness(prompt_builder=None)
    msgs = h._build("task", recent_steps=[], last_feedback="")
    system = "\n".join(m["content"] for m in msgs if m["role"] == "system")
    assert system.strip() == ""             # unchanged legacy behavior
