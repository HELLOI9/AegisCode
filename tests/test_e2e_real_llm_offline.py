"""Offline guard for the e2e harness's VERIFY logic. Never touches a real
provider or the network — that is the human-triggered `make e2e-real-llm`."""
import importlib.util, pathlib

def _load():
    p = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "e2e_real_llm.py"
    spec = importlib.util.spec_from_file_location("e2e_real_llm", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def test_verify_passes_on_green_fixture(tmp_path):
    m = _load()
    (tmp_path / "add.py").write_text("def add(a,b): return a+b\n")
    (tmp_path / "test_add.py").write_text(
        "from add import add\n"
        "def test_a(): assert add(1,2)==3\n"
    )
    checks = m.verify(str(tmp_path), provider_name="OpenAIAdapter", completed=True,
                      pytest_passed=True)
    assert all(checks.values()), checks

def test_verify_fails_when_provider_is_mock(tmp_path):
    m = _load()
    (tmp_path / "add.py").write_text("x")
    (tmp_path / "test_add.py").write_text("x")
    checks = m.verify(str(tmp_path), provider_name="MockLLM", completed=True,
                      pytest_passed=True)
    assert checks["real_provider"] is False

def test_verify_fails_when_pytest_not_passed(tmp_path):
    m = _load()
    (tmp_path / "add.py").write_text("x")
    (tmp_path / "test_add.py").write_text("x")
    checks = m.verify(str(tmp_path), provider_name="OpenAIAdapter", completed=True,
                      pytest_passed=False)
    assert checks["pytest_passed"] is False

def test_verify_fails_when_files_missing(tmp_path):
    m = _load()
    checks = m.verify(str(tmp_path), provider_name="OpenAIAdapter", completed=True,
                      pytest_passed=True)
    assert checks["add_py_exists"] is False and checks["test_add_py_exists"] is False

def test_makefile_e2e_target_not_in_test():
    mk = pathlib.Path("Makefile").read_text()
    assert "e2e-real-llm:" in mk
    # e2e must NOT be a prerequisite of the test target
    test_line = [l for l in mk.splitlines() if l.startswith("test:")][0]
    assert "e2e" not in test_line
