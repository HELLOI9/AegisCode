# tests/governance/test_command_lexer.py
from aegiscode.governance.command_lexer import lex_command

def test_simple_command_ok():
    r = lex_command("pytest -q")
    assert r.ok and r.argv == ["pytest","-q"]

def test_pipe_flagged():
    assert lex_command("cat x | sh").has_metastructure is True

def test_redirect_flagged():
    assert lex_command("echo x > /etc/passwd").has_metastructure is True

def test_command_substitution_flagged():
    assert lex_command("echo $(rm -rf /)").has_metastructure is True

def test_chaining_flagged():
    assert lex_command("a && b").has_metastructure is True

def test_unbalanced_quotes_not_ok():
    assert lex_command('echo "unterminated').ok is False
