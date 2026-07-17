import inspect
from aegiscode.tools.file_tools import WriteFileTool, ReadFileTool, ListFilesTool, SearchTextTool
from aegiscode.tools.command_tool import RunCommandTool
from aegiscode.tools.run_tests_tool import RunTestsTool
from aegiscode.tools.finish_tool import FinishTool

_REQUIRED = {
    WriteFileTool: {"path", "content"},
    ReadFileTool: {"path"},
    ListFilesTool: set(),          # path optional
    SearchTextTool: {"query"},
    RunCommandTool: {"command"},
    RunTestsTool: set(),
    FinishTool: set(),
}

def test_every_tool_has_nonempty_description():
    for cls in _REQUIRED:
        assert isinstance(cls.description, str) and cls.description.strip()

def test_parameters_declare_required_fields_matching_run():
    for cls, required in _REQUIRED.items():
        params = cls.parameters
        assert isinstance(params, dict)
        declared_required = {k for k, v in params.items() if v.get("required")}
        assert declared_required == required, f"{cls.__name__}: {declared_required} != {required}"

def test_parameter_names_are_read_by_run_source():
    # Guard against schema/behavior drift: every declared param name must appear
    # in the tool's run() source (it indexes arguments[<name>] or .get(<name>)).
    for cls in _REQUIRED:
        src = inspect.getsource(cls.run)
        for pname in cls.parameters:
            assert pname in src, f"{cls.__name__}.run does not reference {pname!r}"
