from aegiscode.credentials.scanner import scan_text, scan_paths

def test_detects_planted_key():
    f = scan_text("x = 'sk-abcdef1234567890abcdef1234567890'")
    assert f and f[0].pattern

def test_clean_text_no_findings():
    assert scan_text("no secrets here") == []

def test_scan_file(tmp_path):
    p = tmp_path/"c.py"; p.write_text("KEY=AKIAIOSFODNN7EXAMPLE\n")
    assert scan_paths([str(p)])[0].line_no == 1

def test_detects_quoted_generic_assignment():
    # A quote after `=` previously broke the generic KEY=/SECRET= pattern.
    f = scan_text('api_key = "hunter2secretvalue12345"')
    assert f, "quoted generic assignment must be flagged"

def test_detects_quoted_openai_project_key():
    f = scan_text("SECRET_KEY = 'sk-proj-1a2B3c4D_5e6F-7g8H9i0JklmnopQRs'")
    assert f, "quoted sk-proj- key must be flagged"

def test_detects_unquoted_openai_project_key():
    f = scan_text("OPENAI_KEY=sk-proj-1a2B3c4D_5e6F-7g8H9i0JklmnopQRs")
    assert f

def test_detects_svcacct_key():
    f = scan_text("k = sk-svcacct-abc123DEF456ghi789_JKL-012mno")
    assert f

def test_clean_identifier_line_still_no_new_findings():
    # A plain assignment to a short value / method call must not be flagged.
    assert scan_text("count = 3") == []
    assert scan_text("result = compute()") == []
