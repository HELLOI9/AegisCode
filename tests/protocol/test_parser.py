# tests/protocol/test_parser.py
import pytest
from aegiscode.protocol.parser import parse_action, ActionParseError

def test_parses_fenced_json():
    a = parse_action('reasoning...\n```json\n{"tool":"read_file","arguments":{"path":"a.py"}}\n```')
    assert a.tool == "read_file" and a.arguments["path"] == "a.py"

def test_parses_trailing_object_without_fence():
    a = parse_action('I will read it {"tool":"list_files","arguments":{}}')
    assert a.tool == "list_files"

def test_missing_tool_raises():
    with pytest.raises(ActionParseError):
        parse_action('{"arguments":{}}')

def test_malformed_json_raises():
    with pytest.raises(ActionParseError):
        parse_action('not json at all')
