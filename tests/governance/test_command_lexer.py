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

def test_glob_star_flagged():
    assert lex_command("rm *").has_metastructure is True

def test_glob_question_and_bracket_flagged():
    assert lex_command("cat file?.txt").has_metastructure is True
    assert lex_command("ls [abc].py").has_metastructure is True

def test_newline_injection_flagged():
    assert lex_command("echo safe\nrm -rf /").has_metastructure is True

def test_spaceless_pipe_and_chaining_flagged():
    assert lex_command("echo hi|sh").has_metastructure is True
    assert lex_command("a&&b").has_metastructure is True
    assert lex_command("a;b").has_metastructure is True

def test_backtick_flagged():
    assert lex_command("echo `id`").has_metastructure is True

def test_plain_command_still_ok():
    r = lex_command("pytest -q")
    assert r.ok is True and r.has_metastructure is False and r.argv == ["pytest", "-q"]
