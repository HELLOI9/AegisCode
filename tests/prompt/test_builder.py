from aegiscode.config.schema import AegisConfig
from aegiscode.prompt.builder import PromptBuilder
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.file_tools import WriteFileTool, ReadFileTool
from aegiscode.tools.finish_tool import FinishTool

def _pb(enabled=("write_file", "read_file", "finish")):
    cfg = AegisConfig()
    reg = ToolRegistry()
    classes = {"write_file": WriteFileTool, "read_file": ReadFileTool, "finish": FinishTool}
    for n in enabled:
        reg.register(classes[n]())
    return PromptBuilder(cfg, reg), cfg

def test_system_prompt_states_identity_and_no_direct_access():
    pb, _ = _pb()
    sp = pb.system_prompt(remaining_steps=10)
    assert "AegisCode" in sp
    assert "coding agent" in sp.lower()
    assert "file system" in sp.lower() or "filesystem" in sp.lower()
    assert "shell" in sp.lower()

def test_system_prompt_states_one_action_and_finish_gate():
    pb, _ = _pb()
    sp = pb.system_prompt(remaining_steps=10)
    assert "one" in sp.lower() and "action" in sp.lower()
    assert "pytest" in sp.lower()
    assert "finish" in sp.lower()
    assert "10" in sp  # remaining steps surfaced

def test_system_prompt_renders_workspace_boundary_from_config():
    pb, cfg = _pb()
    sp = pb.system_prompt(remaining_steps=5)
    for pat in cfg.governance.sensitive_file_patterns:
        assert pat in sp                       # .env / *.pem / *.key / *credentials* / .git/
    for cmd in cfg.governance.command_allowlist:
        assert cmd in sp                       # allowlist rendered concretely

def test_tool_protocol_has_action_schema_and_registry_tools():
    pb, _ = _pb()
    tp = pb.tool_protocol()
    assert "json" in tp.lower()
    for field in ("thought", "tool", "arguments", "expectation"):
        assert field in tp
    assert "write_file" in tp and "read_file" in tp and "finish" in tp

def test_tool_protocol_omits_disabled_tools():
    pb, _ = _pb(enabled=("read_file", "finish"))  # write_file disabled
    tp = pb.tool_protocol()
    assert "read_file" in tp
    assert "write_file" not in tp

def test_prompt_contains_no_secret_material():
    pb, _ = _pb()
    blob = pb.system_prompt(10) + "\n" + pb.tool_protocol()
    for bad in ("sk-", "api_key", "authorization", "bearer"):
        assert bad.lower() not in blob.lower()

def test_system_prompt_guides_no_repeat_and_finish_after_pass():
    pb, _ = _pb()
    sp = pb.system_prompt(remaining_steps=10)
    low = sp.lower()
    # 不要重复已成功的动作（NO_PROGRESS 引导）
    assert "repeat" in low or "重复" in sp
    assert "no_progress" in low or "no progress" in low or "无进展" in sp
    # 测试通过后必须 finish
    assert "finish" in low
    assert "pass" in low or "通过" in sp
