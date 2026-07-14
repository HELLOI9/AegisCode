from aegiscode.credentials.scanner import scan_text, scan_paths

def test_detects_planted_key():
    f = scan_text("x = 'sk-abcdef1234567890abcdef1234567890'")
    assert f and f[0].pattern

def test_clean_text_no_findings():
    assert scan_text("no secrets here") == []

def test_scan_file(tmp_path):
    p = tmp_path/"c.py"; p.write_text("KEY=AKIAIOSFODNN7EXAMPLE\n")
    assert scan_paths([str(p)])[0].line_no == 1
