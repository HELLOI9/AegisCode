# AegisCode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build AegisCode — a policy-governed coding agent harness whose safety governance is a deterministic, unit-testable, auditable policy engine.

**Architecture:** Self-implemented agent main loop (strict single-action per turn) calling a pluggable `LLMClient`, parsing one structured Action, running it through an ordered first-match policy engine (command lexical governance 甲 + path fence 乙 + HITL approval), dispatching to a small tool registry, classifying objective feedback (pytest/exit-code/file-scope), and re-injecting redacted feedback. Every action is recorded in an append-only SHA256 hash-chained audit stream. WebUI → REST API → Application Service → Harness Core; SQLite persistence; credentials via keyring/.env/env.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, stdlib `sqlite3` (hand-written SQL), pytest, PyYAML, keyring, Docker, native HTML/CSS/JS. LLM via unified `LLMClient` with OpenAIAdapter / AnthropicAdapter / MockLLM.

## Global Constraints

- Python 3.12; every core mechanism must be unit-testable with MockLLM, no network, no real LLM (SPEC §16.1).
- Six dimensions (decision/tools/memory/governance/feedback/config) all have a minimum implementation; only governance is deepened (SPEC §2, §11).
- TDD is mandatory: red → green → refactor. No implementation before a failing test (course §4.6).
- Governance logic is deterministic code, never a prompt (SPEC §10.5). Every DENY/APPROVAL decision carries a unique `rule_id` + `reason`.
- Commands are executed `shell=False` with an argv array, cwd locked to workspace; never `shell=True` (SPEC §11.2).
- API keys never hardcoded, never committed, never logged. Redactor covers logs/audit/feedback/memory (SPEC §12).
- Linux path semantics only (Windows case-folding out of scope).
- Single stack: Python + pytest target projects only.
- One-command tests: `make test`. CI must contain a job named `unit-test`.
- Default thresholds (YAML-overridable): `max_steps=25`, `max_consecutive_failures=5`, `no_progress_repeat_limit=3`, `action_retry_limit=3`.

---

## File Structure

```
aegiscode/
  __init__.py
  config/
    schema.py          # Pydantic config models (T2)
    loader.py          # YAML load + validate + env overrides (T2)
  security/
    redactor.py        # deterministic secret/path redaction (T3)
  persistence/
    db.py              # sqlite3 connection, schema loading, WAL (T4)
    schema.sql         # DDL for all 6 tables, loaded by db.py (T4)
    repositories.py    # tasks/steps/approvals/audit/memories CRUD (T26)
  llm/
    base.py            # LLMClient interface (T5)
    mock.py            # MockLLM scripted queue + message recorder (T5)
    openai_adapter.py  # OpenAIAdapter (T6)
    anthropic_adapter.py # AnthropicAdapter (T6)
  protocol/
    action.py          # Action Pydantic model (T7)
    parser.py          # robust JSON extraction + validation → INVALID_ACTION (T7)
  tools/
    base.py            # Tool interface (T8)
    result.py          # ToolResult model (T8)
    registry.py        # registration + lookup (T8)
    file_tools.py      # list_files/read_file/search_text/write_file (T9)
    command_tool.py    # run_command executor (shell=False) (T16)
    run_tests_tool.py  # run_tests sensor (T17)
    finish_tool.py     # finish control tool (T17)
  governance/
    decision.py        # Decision enum (T10)
    engine.py          # ordered first-match PolicyEngine (T10)
    path_fence.py      # 乙 realpath + membership + sensitive blacklist (T11)
    dispatcher.py      # governed dispatcher (path fence + tiers + no-exec on DENY/APPROVAL) (T12)
    command_lexer.py   # 甲 shlex parse + metastructure detection (T13)
    command_rules.py   # 甲 allowlist + dangerous-arg rules (T14)
    approval.py        # HITL ApprovalRequest state machine + `fingerprint()` helper (T15)
  feedback/
    classifier.py      # 8-class failure classification + ProgressTracker (T18)
    pytest_parser.py   # pytest output → concise detail_for_llm (T18)
  audit/
    events.py          # EventType enum (T19)
    chain.py           # AuditLog: SHA256 hash chain + verify_chain (T19)
  memory/
    store.py           # memories write(secret-refused)/retrieve(type+project+topK) (T20)
    context_builder.py # 6-tier budget assembly + deterministic summarize_step (T21)
  loop/
    termination.py     # TerminationReason enum + LoopCounters + decide_termination (T22)
    harness.py         # HarnessCore main loop (T23)
  credentials/
    store.py           # keyring/.env/env layered store (T24)
    scanner.py         # self-written secret pattern scanner (T25)
  service/
    app_service.py     # ApplicationService: create/query/approve/cancel (T26)
    api.py             # FastAPI REST (8 endpoints) (T27)
    webui/             # static HTML/CSS/JS (T28)
  cli.py               # init/run/serve/config/key/demo (T29)
demos/                 # mechanism demo scripts (T31)
tests/                 # mirrors package layout
Dockerfile             # (T30)
.gitlab-ci.yml         # unit-test job (T32)
Makefile               # make test (T1)
aegis.yaml             # sample config (T2)
```

> **Note on `fingerprint()`:** the action-fingerprint helper (used by approval-supersede and no-progress detection) lives in `governance/approval.py` (T15). There is no standalone `fingerprint.py` file.

## Environment Bootstrap (do this once, before Task 1)

Every task's Step 2 uses `pytest`, so `pytest` must exist before Step 2 can produce the predicted "module not found: aegiscode" failure. On a cold machine, pick whichever isolation tool actually works on your box:

```bash
# Option A (most portable — no system packages needed):
conda create -p ./.condaenv python=3.12 && conda activate ./.condaenv
# Option B (uv):
uv venv --python 3.12 .venv && source .venv/bin/activate
# (uv ships without pip; use `uv pip install ...` instead of `python -m pip ...` below)
# Option C (stdlib venv — requires the python3.12-venv system package;
#   on Debian/Ubuntu run `sudo apt install python3.12-venv` first, else ensurepip fails):
python3.12 -m venv .venv && source .venv/bin/activate

python -m pip install --upgrade pip pytest    # under Option B use: uv pip install pytest
```

After Task 1's `pyproject.toml` exists, `pip install -e ".[dev]"` supersedes the manual `pytest` install. If none of A/B/C is available, install pyenv/uv/conda first — the plan targets Python 3.12 only.

## Dependency Graph & Parallelization

**Milestone 0 — Foundations**
- T1 scaffold → blocks everything.
- After T1, parallel: **T2 config**, **T3 redactor**, **T4 persistence**.

**Milestone 1 — Decision & Tools substrate**
- T5 LLM base+Mock (after T1) ∥ T7 action model+parser (after T1).
- T6 real adapters (after T5).
- T8 tool base+registry+finish (after T1) → T9 file tools (after T8).

**Milestone 2 — Governance (main contribution, 6 split tasks)**
- T10 decision+engine (after T1) → prerequisite for T11, T12, T15.
- **T11 path fence** ∥ **T13 command lexer** (both after T1; T11 also needs T10 for verdict types).
- T12 governed dispatcher (after T10, T11, T8).
- T14 command rules (after T13).
- T15 approval state machine + `fingerprint()` (after T10).
- T16 command tool executor (after T14, T8) ∥ T17 run_tests + finish (after T8).

**Milestone 3 — Feedback / Audit / Memory**
- T18 feedback classifier + pytest parser (after T3 redactor, T8).
- T19 audit chain (after T3 redactor, T4 persistence).
- T20 memory store (after T4 persistence, T25 scanner) → T21 context builder (after T20).

**Milestone 4 — Core loop**
- T22 termination (after T1).
- T23 HarnessCore — the integration task; after **T5, T7, T8, T9, T12, T14, T15, T16, T17, T18, T19, T21, T22** (T10/T11/T13 enter transitively via T12/T14).

**Milestone 5 — Credentials**
- T24 credential store ∥ T25 secret scanner (both after T1).

**Milestone 6 — Service / Interface**
- T26 app service (after T23, T4 persistence) → T27 REST API (after T26) → T28 WebUI (after T27).
- T29 CLI (after T23, T24) — parallel with T27/T28.

**Milestone 7 — Distribution & Demos**
- T30 Dockerfile (after T27) ∥ T32 CI (after T1, needs make test).
- T31 mechanism demos (after T23 + governance set).

**Parallel-safe worktree groups:** {T2,T3,T4} · {T5,T7,T8} · {T11,T13} · {T16,T17} · {T24,T25}.
(T25 scanner should precede T20 memory store — T20 imports `scan_text`.)

---

# Milestone 0 — Foundations

### Task 1: Project scaffold + Makefile + package skeleton ✅ DONE (c6f8f28)

**Files:**
- Create: `pyproject.toml`, `aegiscode/__init__.py`, `Makefile`, `tests/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Produces: importable `aegiscode` package; `make test` running pytest.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_smoke.py
import aegiscode

def test_package_version():
    assert aegiscode.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Prereq: complete the "Environment Bootstrap" block above (pytest must be installed).
Run: `pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aegiscode'`
(If instead you see `No module named pytest`, you skipped the bootstrap; run it and re-try Step 2.)

- [ ] **Step 3: Write minimal implementation**
```toml
# pyproject.toml
[project]
name = "aegiscode"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["fastapi>=0.110", "uvicorn>=0.29", "pydantic>=2.6",
                "pyyaml>=6.0", "keyring>=24.0", "httpx>=0.27"]
[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.4", "mypy>=1.9"]
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
[tool.setuptools.packages.find]
include = ["aegiscode*"]
```
```python
# aegiscode/__init__.py
__version__ = "0.1.0"
```
```makefile
# Makefile
.PHONY: test
test:
	pytest -q
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e ".[dev]" && make test`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add pyproject.toml aegiscode/__init__.py Makefile tests/
git commit -m "chore: project scaffold + make test"
```

---

### Task 2: Config schema + YAML loader ✅ DONE (387c632, fix 4cf0126)

**Files:**
- Create: `aegiscode/config/__init__.py`, `aegiscode/config/schema.py`, `aegiscode/config/loader.py`, `aegis.yaml`, `tests/config/test_loader.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `AegisConfig` (Pydantic model, fields per SPEC §11 M11 YAML: `workspace`, `limits`, `tools`, `feedback`, `governance`, `memory`, `credentials`, `llm`) with **`extra="forbid"` on every nested model** (SPEC M11 边界); `CommandRule(BaseModel)` with fields `argv0: str`, `args_contain: list[str] = []`, `decision: Decision` (a `str, Enum` of the four tiers, defined in this task); `DefaultDecisions.readonly/write/command` typed as the same `Decision` enum. `load_config(path: str, env: dict|None=None) -> AegisConfig`: when `env is None`, defaults to `os.environ`; recognizes exactly two overrides — `AEGIS_LLM_PROVIDER` and `AEGIS_LLM_MODEL`; raises `ConfigError` on any invalid YAML or Pydantic validation failure (including unknown fields, wrong types, out-of-enum values).

- [ ] **Step 1: Write the failing test**
```python
# tests/config/test_loader.py
import pytest
from aegiscode.config.loader import load_config, ConfigError

def test_loads_defaults_and_overrides(tmp_path):
    (tmp_path / "aegis.yaml").write_text(
        "workspace:\n  root: /workspace\n"
        "limits:\n  max_steps: 25\n  max_consecutive_failures: 5\n  no_progress_repeat_limit: 3\n"
        "llm:\n  provider: openai\n  model: gpt-4o\n"
    )
    cfg = load_config(str(tmp_path / "aegis.yaml"), env={})
    assert cfg.limits.max_steps == 25
    assert cfg.governance.default_decisions.command == "DENY"

def test_unknown_top_level_field_raises(tmp_path):
    (tmp_path / "aegis.yaml").write_text("bogus_top_field: 1\n")
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "aegis.yaml"), env={})

def test_unknown_nested_field_raises(tmp_path):
    (tmp_path / "aegis.yaml").write_text("governance:\n  totally_made_up: true\n")
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "aegis.yaml"), env={})

def test_bad_decision_tier_raises(tmp_path):
    (tmp_path / "aegis.yaml").write_text(
        "governance:\n  default_decisions:\n    command: NONSENSE_TIER\n"
    )
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "aegis.yaml"), env={})

def test_command_rules_flat_shape(tmp_path):
    (tmp_path / "aegis.yaml").write_text(
        "governance:\n  command_rules:\n"
        "    - {argv0: pip, args_contain: [install], decision: REQUIRE_APPROVAL}\n"
    )
    cfg = load_config(str(tmp_path / "aegis.yaml"), env={})
    assert cfg.governance.command_rules[0].argv0 == "pip"
    assert cfg.governance.command_rules[0].decision == "REQUIRE_APPROVAL"

def test_command_rules_reject_nested_match(tmp_path):
    (tmp_path / "aegis.yaml").write_text(
        "governance:\n  command_rules:\n"
        "    - {match: {argv0: git, args_contain: [push]}, decision: DENY}\n"
    )
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "aegis.yaml"), env={})

def test_type_error_raises(tmp_path):
    (tmp_path / "aegis.yaml").write_text("limits:\n  max_steps: not_an_int\n")
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "aegis.yaml"), env={})

def test_env_overrides_provider_and_model(tmp_path):
    (tmp_path / "aegis.yaml").write_text("llm:\n  provider: openai\n  model: gpt-4o\n")
    cfg = load_config(str(tmp_path / "aegis.yaml"),
                      env={"AEGIS_LLM_PROVIDER": "anthropic", "AEGIS_LLM_MODEL": "claude-x"})
    assert cfg.llm.provider == "anthropic" and cfg.llm.model == "claude-x"

def test_env_none_reads_os_environ(tmp_path, monkeypatch):
    # env=None must fall back to os.environ (SPEC §11 M11); guard the default branch.
    (tmp_path / "aegis.yaml").write_text("llm:\n  provider: openai\n  model: gpt-4o\n")
    monkeypatch.setenv("AEGIS_LLM_MODEL", "claude-from-os-env")
    cfg = load_config(str(tmp_path / "aegis.yaml"))   # env omitted → None → os.environ
    assert cfg.llm.model == "claude-from-os-env"
```

- [ ] **Step 2: Run test to verify it fails**

Prereq: environment bootstrap done.
Run: `pytest tests/config/test_loader.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/config/schema.py
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field

class Decision(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_WITH_AUDIT = "ALLOW_WITH_AUDIT"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Limits(_Strict):
    max_steps: int = 25
    max_consecutive_failures: int = 5
    no_progress_repeat_limit: int = 3
    action_retry_limit: int = 3
    command_timeout_sec: int = 30
    output_max_bytes: int = 65536

class DefaultDecisions(_Strict):
    readonly: Decision = Decision.ALLOW
    write: Decision = Decision.REQUIRE_APPROVAL
    command: Decision = Decision.DENY

class CommandRule(_Strict):
    argv0: str
    args_contain: list[str] = []
    decision: Decision

# Canonical dangerous-command rules — baked into code defaults so governance is
# secure-by-default even with NO aegis.yaml present (SPEC §A.4B: mechanism is code,
# not config content). A YAML `command_rules:` list fully REPLACES this default
# (declarative override), so if a user supplies rules they own the whole list.
_DEFAULT_COMMAND_RULES: list["CommandRule"] = [
    CommandRule(argv0="git",    args_contain=["push"],           decision=Decision.DENY),
    CommandRule(argv0="git",    args_contain=["reset", "--hard"],decision=Decision.DENY),
    CommandRule(argv0="git",    args_contain=["clean"],          decision=Decision.DENY),
    CommandRule(argv0="git",    args_contain=["commit"],         decision=Decision.REQUIRE_APPROVAL),
    CommandRule(argv0="pip",    args_contain=["install"],        decision=Decision.REQUIRE_APPROVAL),
    CommandRule(argv0="python", args_contain=["-c"],             decision=Decision.DENY),
    CommandRule(argv0="python", args_contain=["-m"],             decision=Decision.DENY),
]

class Governance(_Strict):
    command_allowlist: list[str] = ["python", "python3", "pip", "pytest", "ruff", "mypy", "git", "ls", "cat"]
    command_rules: list[CommandRule] = Field(default_factory=lambda: list(_DEFAULT_COMMAND_RULES))  # baked-in; YAML fully overrides
    sensitive_file_patterns: list[str] = [".env", ".git/", "*.pem", "*.key", "*credentials*"]
    write_allowlist_dirs: list[str] = ["src/", "tests/"]
    default_decisions: DefaultDecisions = DefaultDecisions()

class Workspace(_Strict):
    root: str = "/workspace"

class Tools(_Strict):
    enabled: list[str] = ["list_files","read_file","search_text","write_file","run_tests","run_command","finish"]
    write_max_bytes: int = 1048576

class Feedback(_Strict):
    test_command: str = "pytest -q"
    target_tests: str = "tests/"

class Memory(_Strict):
    retrieval_top_k: int = 8
    context_budget_chars: int = 24000

class Credentials(_Strict):
    allow_dotenv: bool = False

class Llm(_Strict):
    provider: str = "openai"
    model: str = "gpt-4o"
    base_url: str | None = None

class AegisConfig(_Strict):
    workspace: Workspace = Workspace()
    limits: Limits = Limits()
    tools: Tools = Tools()
    feedback: Feedback = Feedback()
    governance: Governance = Governance()
    memory: Memory = Memory()
    credentials: Credentials = Credentials()
    llm: Llm = Llm()
```
```python
# aegiscode/config/loader.py
import os
import yaml
from pydantic import ValidationError
from .schema import AegisConfig

class ConfigError(Exception): ...

# Exactly two env-var overrides are recognized (SPEC §11 M11):
_ENV_MAP = {"AEGIS_LLM_PROVIDER": ("llm", "provider"),
            "AEGIS_LLM_MODEL":    ("llm", "model")}

def load_config(path: str, env: dict | None = None) -> AegisConfig:
    try:
        raw = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML: {e}") from e
    src = os.environ if env is None else env
    for key, (section, field) in _ENV_MAP.items():
        if key in src:
            raw.setdefault(section, {})[field] = src[key]
    try:
        return AegisConfig(**raw)
    except ValidationError as e:
        raise ConfigError(str(e)) from e
```
(Also create `aegis.yaml` as a sample with the full 8-section structure from SPEC §11 M11.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/config/test_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/config aegis.yaml tests/config
git commit -m "feat: config schema + YAML loader with validation"
```

---

### Task 3: Redactor (deterministic secret/path scrubber) ✅ DONE (aa8111d, +f214e4c)

**Files:**
- Create: `aegiscode/security/__init__.py`, `aegiscode/security/redactor.py`, `tests/security/test_redactor.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `redact(text: str, workspace_root: str|None=None) -> str` — replaces API-key patterns (`sk-...`, `sk-ant-...`, `AKIA...`, generic 32+ hex/base64 tokens after `KEY=`/`TOKEN=`/`PASSWORD=`), and rewrites absolute paths starting with workspace_root to relative form.

- [ ] **Step 1: Write the failing test**
```python
# tests/security/test_redactor.py
from aegiscode.security.redactor import redact

def test_redacts_openai_key():
    assert "sk-abcdef1234567890abcdef1234567890" not in redact("token=sk-abcdef1234567890abcdef1234567890")

def test_redacts_anthropic_key():
    out = redact("KEY=sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXX")
    assert "sk-ant-" not in out

def test_redacts_aws_key():
    assert "AKIAIOSFODNN7EXAMPLE" not in redact("AWS AKIAIOSFODNN7EXAMPLE done")

def test_rewrites_workspace_absolute_paths():
    out = redact("failed at /workspace/src/foo.py:12", workspace_root="/workspace")
    assert "/workspace" not in out
    assert "src/foo.py" in out

def test_no_change_when_clean():
    assert redact("hello world") == "hello world"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/security/test_redactor.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/security/redactor.py
import re

_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(?:KEY|TOKEN|PASSWORD|SECRET)\s*=\s*[A-Za-z0-9\-_+/=]{16,}"),
]

def redact(text: str, workspace_root: str | None = None) -> str:
    out = text
    for p in _PATTERNS:
        out = p.sub("[REDACTED]", out)
    if workspace_root:
        out = out.replace(workspace_root.rstrip("/") + "/", "")
        out = out.replace(workspace_root, "")
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/security/test_redactor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/security tests/security
git commit -m "feat: deterministic redactor for keys and workspace paths"
```

---

### Task 4: Persistence layer — SQLite schema + connection ✅ DONE (158a744)

**Files:**
- Create: `aegiscode/persistence/__init__.py`, `aegiscode/persistence/db.py`, `aegiscode/persistence/schema.sql`, `tests/persistence/test_db.py`

**Interfaces:**
- Consumes: `AegisConfig` (indirectly for path).
- Produces: `open_db(path: str) -> sqlite3.Connection` with WAL mode + all 6 tables from SPEC §9 created (`tasks`, `steps`, `approval_requests`, `audit_events`, `memories`, `task_snapshots`).

- [ ] **Step 1: Write the failing test**
```python
# tests/persistence/test_db.py
from aegiscode.persistence.db import open_db

def test_all_six_tables_exist(tmp_path):
    conn = open_db(str(tmp_path / "aegis.sqlite"))
    got = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"tasks","steps","approval_requests",
            "audit_events","memories","task_snapshots"} <= got

def test_wal_mode(tmp_path):
    conn = open_db(str(tmp_path / "aegis.sqlite"))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/persistence/test_db.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```sql
-- aegiscode/persistence/schema.sql
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY, workspace_path TEXT, workspace_hash TEXT,
  task_description TEXT, state TEXT, termination_reason TEXT,
  step_count INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS steps (
  step_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, step_index INTEGER,
  action_json TEXT, governance_decision TEXT, triggered_rule_id TEXT,
  tool_result_json TEXT, feedback_category TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS approval_requests (
  approval_id TEXT PRIMARY KEY, task_id TEXT, step_index INTEGER,
  action_snapshot_json TEXT, action_fingerprint TEXT,
  governance_decision TEXT, triggered_rule_id TEXT, reason TEXT,
  risk_explanation TEXT, state TEXT, remember_choice INTEGER DEFAULT 0,
  created_at TEXT, decided_at TEXT, decided_by TEXT);
CREATE TABLE IF NOT EXISTS audit_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
  step_index INTEGER, timestamp TEXT, event_type TEXT,
  payload_json TEXT, prev_hash TEXT, hash TEXT);
CREATE TABLE IF NOT EXISTS memories (
  memory_id TEXT PRIMARY KEY, project_id TEXT, type TEXT, key TEXT,
  value TEXT, tags_json TEXT, source TEXT, confirmed INTEGER,
  created_at TEXT, last_used_at TEXT, use_count INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS task_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
  step_index INTEGER, file_path TEXT, snapshot_path TEXT, created_at TEXT);
```
```python
# aegiscode/persistence/db.py
import sqlite3, pathlib

def open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    sql = pathlib.Path(__file__).with_name("schema.sql").read_text()
    conn.executescript(sql)
    return conn
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/persistence/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/persistence tests/persistence
git commit -m "feat: SQLite persistence with 6-table schema + WAL"
```

---

## Milestone 1 — LLM abstraction, action protocol, tools

### Task 5: LLMClient interface + MockLLM ✅ DONE (597a8ac, fix 014cb16)

**Files:**
- Create: `aegiscode/llm/__init__.py`, `aegiscode/llm/base.py`, `aegiscode/llm/mock.py`, `tests/llm/test_mock.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `class LLMClient(ABC)` with `complete(messages: list[dict]) -> str`; `class MockLLM(LLMClient)` taking `scripted_responses: list[str]`, exposing `received_messages: list[list[dict]]`, raising `MockExhaustedError` when the queue is empty.

- [ ] **Step 1: Write the failing test**
```python
# tests/llm/test_mock.py
import pytest
from aegiscode.llm.mock import MockLLM, MockExhaustedError

def test_returns_scripted_in_order():
    m = MockLLM(["a", "b"])
    assert m.complete([{"role":"user","content":"x"}]) == "a"
    assert m.complete([{"role":"user","content":"y"}]) == "b"

def test_records_received_messages():
    m = MockLLM(["a"])
    m.complete([{"role":"user","content":"hi"}])
    assert m.received_messages[0][0]["content"] == "hi"

def test_raises_when_exhausted():
    m = MockLLM([])
    with pytest.raises(MockExhaustedError):
        m.complete([])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm/test_mock.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/llm/base.py
from abc import ABC, abstractmethod

class LLMClient(ABC):
    @abstractmethod
    def complete(self, messages: list[dict]) -> str: ...
```
```python
# aegiscode/llm/mock.py
from aegiscode.llm.base import LLMClient

class MockExhaustedError(RuntimeError): ...

class MockLLM(LLMClient):
    def __init__(self, scripted_responses: list[str]):
        self._queue = list(scripted_responses)
        self.received_messages: list[list[dict]] = []
    def complete(self, messages: list[dict]) -> str:
        self.received_messages.append(messages)
        if not self._queue:
            raise MockExhaustedError("no scripted responses left")
        return self._queue.pop(0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm/test_mock.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/llm tests/llm
git commit -m "feat: LLMClient interface + MockLLM with message recording"
```

---

### Task 6: OpenAI + Anthropic adapters ✅ DONE (a7355d8, fix 034f39e)

**Files:**
- Create: `aegiscode/llm/openai_adapter.py`, `aegiscode/llm/anthropic_adapter.py`, `tests/llm/test_adapters.py`

**Interfaces:**
- Consumes: `LLMClient`.
- Produces: `OpenAIAdapter(model, api_key, base_url=None)` and `AnthropicAdapter(model, api_key)`, each `LLMClient`. Both take an injectable `http_post` callable (default = real HTTP) so tests never touch the network. Each translates `messages` to the vendor wire format and extracts the completion text.

- [ ] **Step 1: Write the failing test** (inject a fake `http_post`)
```python
# tests/llm/test_adapters.py
from aegiscode.llm.openai_adapter import OpenAIAdapter
from aegiscode.llm.anthropic_adapter import AnthropicAdapter

def fake_openai_post(url, headers, json):
    return {"choices":[{"message":{"content":"OK-OAI"}}]}

def fake_anthropic_post(url, headers, json):
    return {"content":[{"type":"text","text":"OK-ANT"}]}

def test_openai_extracts_text():
    a = OpenAIAdapter("gpt-4o","k", http_post=fake_openai_post)
    assert a.complete([{"role":"user","content":"hi"}]) == "OK-OAI"

def test_anthropic_extracts_text_and_splits_system():
    seen = {}
    def cap(url, headers, json): seen.update(json); return {"content":[{"type":"text","text":"OK-ANT"}]}
    a = AnthropicAdapter("claude-x","k", http_post=cap)
    out = a.complete([{"role":"system","content":"S"},{"role":"user","content":"U"}])
    assert out == "OK-ANT"
    assert seen["system"] == "S"                     # system pulled out of messages
    assert all(m["role"] != "system" for m in seen["messages"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm/test_adapters.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/llm/openai_adapter.py
from aegiscode.llm.base import LLMClient

def _real_post(url, headers, json):
    import urllib.request, json as _j
    req = urllib.request.Request(url, data=_j.dumps(json).encode(),
        headers={**headers, "Content-Type":"application/json"})
    with urllib.request.urlopen(req) as r:
        return _j.loads(r.read())

class OpenAIAdapter(LLMClient):
    def __init__(self, model, api_key, base_url=None, http_post=_real_post):
        self.model, self.api_key = model, api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self._post = http_post
    def complete(self, messages):
        r = self._post(f"{self.base_url}/chat/completions",
            {"Authorization": f"Bearer {self.api_key}"},
            {"model": self.model, "messages": messages})
        return r["choices"][0]["message"]["content"]
```
```python
# aegiscode/llm/anthropic_adapter.py
from aegiscode.llm.base import LLMClient
from aegiscode.llm.openai_adapter import _real_post

class AnthropicAdapter(LLMClient):
    def __init__(self, model, api_key, http_post=_real_post):
        self.model, self.api_key, self._post = model, api_key, http_post
    def complete(self, messages):
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        r = self._post("https://api.anthropic.com/v1/messages",
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            {"model": self.model, "max_tokens": 4096, "system": system, "messages": convo})
        return "".join(b["text"] for b in r["content"] if b.get("type") == "text")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm/test_adapters.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/llm tests/llm
git commit -m "feat: OpenAI + Anthropic adapters with injectable transport"
```

---

### Task 7: Action model + robust parser ✅ DONE (3362c6d, fix f33e0c2)

**Files:**
- Create: `aegiscode/protocol/__init__.py`, `aegiscode/protocol/action.py`, `aegiscode/protocol/parser.py`, `tests/protocol/test_parser.py`

**Interfaces:**
- Consumes: nothing (pydantic).
- Produces: `class Action(BaseModel)` with `thought:str|None, tool:str, arguments:dict, expectation:str|None`; `parse_action(text:str) -> Action` and exception `ActionParseError`. Extraction rule: prefer a ```json fenced block; else the last balanced `{...}` object; then pydantic-validate.

- [ ] **Step 1: Write the failing test**
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/protocol/test_parser.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/protocol/action.py
from pydantic import BaseModel

class Action(BaseModel):
    tool: str
    arguments: dict = {}
    thought: str | None = None
    expectation: str | None = None
```
```python
# aegiscode/protocol/parser.py
import json, re
from pydantic import ValidationError
from aegiscode.protocol.action import Action

class ActionParseError(ValueError): ...

_FENCE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

def _last_balanced(text: str) -> str | None:
    stack, start = 0, None
    best = None
    for i, c in enumerate(text):
        if c == "{":
            if stack == 0: start = i
            stack += 1
        elif c == "}" and stack:
            stack -= 1
            if stack == 0: best = text[start:i+1]
    return best

def parse_action(text: str) -> Action:
    m = _FENCE.search(text)
    raw = m.group(1) if m else _last_balanced(text)
    if not raw:
        raise ActionParseError("no JSON object found")
    try:
        data = json.loads(raw)
        return Action(**data)
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        raise ActionParseError(str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/protocol/test_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/protocol tests/protocol
git commit -m "feat: Action model + robust JSON parser (fence/last-object)"
```

---

### Task 8: ToolResult model + tool registry & interface ✅ DONE (ccbd1de)

**Files:**
- Create: `aegiscode/tools/__init__.py`, `aegiscode/tools/result.py`, `aegiscode/tools/base.py`, `aegiscode/tools/registry.py`, `tests/tools/test_registry.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `class ToolResult(BaseModel)` (`tool, status, category, summary, detail_for_llm, exit_code, duration_ms, truncated, artifacts`); `class Tool(Protocol)` with `name:str`, `run(arguments:dict, ctx)->ToolResult`; `class ToolRegistry` with `register(tool)`, `get(name)->Tool|None`, `names()->list[str]`.

- [ ] **Step 1: Write the failing test**
```python
# tests/tools/test_registry.py
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.result import ToolResult

class Dummy:
    name = "dummy"
    def run(self, arguments, ctx):
        return ToolResult(tool="dummy", status="success", summary="ok")

def test_register_and_get():
    r = ToolRegistry(); r.register(Dummy())
    assert r.get("dummy").name == "dummy"
    assert "dummy" in r.names()

def test_unknown_returns_none():
    assert ToolRegistry().get("nope") is None

def test_toolresult_defaults():
    tr = ToolResult(tool="t", status="success", summary="s")
    assert tr.truncated is False and tr.category is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_registry.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/tools/result.py
from pydantic import BaseModel
from typing import Any

class ToolResult(BaseModel):
    tool: str
    status: str                       # success|failure|denied|error
    summary: str
    category: str | None = None
    detail_for_llm: str = ""
    exit_code: int | None = None
    duration_ms: int = 0
    truncated: bool = False
    artifacts: dict[str, Any] = {}
```
```python
# aegiscode/tools/base.py
from typing import Protocol
from aegiscode.tools.result import ToolResult

class Tool(Protocol):
    name: str
    def run(self, arguments: dict, ctx) -> ToolResult: ...
```
```python
# aegiscode/tools/registry.py
class ToolRegistry:
    def __init__(self): self._tools = {}
    def register(self, tool): self._tools[tool.name] = tool
    def get(self, name): return self._tools.get(name)
    def names(self): return list(self._tools)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/tools tests/tools
git commit -m "feat: ToolResult model + tool registry and interface"
```

---

### Task 9: File tools (list/read/search/write) — pure IO, no governance ✅ DONE (b65fed1, fix 4e9a98f)

**Files:**
- Create: `aegiscode/tools/file_tools.py`, `tests/tools/test_file_tools.py`

**Interfaces:**
- Consumes: `ToolResult`. Receives an already-validated absolute path from `ctx` (path fencing is Task 12, dispatched before these run).
- Produces: `ListFilesTool`, `ReadFileTool`, `SearchTextTool` (pure-Python recursive walk), `WriteFileTool` (full-overwrite, text-only, size limit via `ctx.write_max_bytes`, snapshot hook via `ctx.snapshot(path)`). Binary read returns `status="success", summary="binary skipped"` (no garbled bytes).

- [ ] **Step 1: Write the failing test**
```python
# tests/tools/test_file_tools.py
from types import SimpleNamespace
from aegiscode.tools.file_tools import ReadFileTool, WriteFileTool, SearchTextTool

def _ctx(tmp_path):
    return SimpleNamespace(resolve=lambda p: str(tmp_path / p),
                           write_max_bytes=1_000_000, snapshot=lambda p: None)

def test_write_then_read(tmp_path):
    ctx = _ctx(tmp_path)
    WriteFileTool().run({"path":"a.py","content":"X=1\n"}, ctx)
    r = ReadFileTool().run({"path":"a.py"}, ctx)
    assert "X=1" in r.detail_for_llm and r.status == "success"

def test_write_rejects_oversize(tmp_path):
    ctx = _ctx(tmp_path); ctx.write_max_bytes = 2
    r = WriteFileTool().run({"path":"a.py","content":"toolong"}, ctx)
    assert r.status == "error"

def test_binary_read_skipped(tmp_path):
    (tmp_path/"b.bin").write_bytes(b"\x00\x01\x02\xff")
    r = ReadFileTool().run({"path":"b.bin"}, _ctx(tmp_path))
    assert "binary" in r.summary.lower()

def test_search_finds_match(tmp_path):
    ctx = _ctx(tmp_path)
    WriteFileTool().run({"path":"a.py","content":"needle here\n"}, ctx)
    r = SearchTextTool().run({"query":"needle"}, ctx)
    assert "a.py" in r.detail_for_llm
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_file_tools.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation** (full-overwrite writer; binary sniff via NUL byte; search walks `ctx.resolve(".")`)
```python
# aegiscode/tools/file_tools.py
import os
from aegiscode.tools.result import ToolResult

def _is_binary(b: bytes) -> bool:
    return b"\x00" in b

class WriteFileTool:
    name = "write_file"
    def run(self, arguments, ctx):
        path, content = arguments["path"], arguments["content"]
        if len(content.encode()) > ctx.write_max_bytes:
            return ToolResult(tool=self.name, status="error", category="TOOL_ERROR",
                              summary="content exceeds write_max_bytes")
        abspath = ctx.resolve(path)
        ctx.snapshot(abspath)
        os.makedirs(os.path.dirname(abspath) or ".", exist_ok=True)
        with open(abspath, "w") as f: f.write(content)
        return ToolResult(tool=self.name, status="success",
                          summary=f"wrote {path}", artifacts={"changed_files":[path]})

class ReadFileTool:
    name = "read_file"
    def run(self, arguments, ctx):
        raw = open(ctx.resolve(arguments["path"]), "rb").read()
        if _is_binary(raw):
            return ToolResult(tool=self.name, status="success", summary="binary skipped")
        text = raw.decode(errors="replace")
        return ToolResult(tool=self.name, status="success",
                          summary=f"read {len(text.splitlines())} lines", detail_for_llm=text)

class ListFilesTool:
    name = "list_files"
    def run(self, arguments, ctx):
        root = ctx.resolve(arguments.get("path","."))
        names = sorted(os.listdir(root))
        return ToolResult(tool=self.name, status="success",
                          summary=f"{len(names)} entries", detail_for_llm="\n".join(names))

class SearchTextTool:
    name = "search_text"
    def run(self, arguments, ctx):
        q, hits = arguments["query"], []
        base = ctx.resolve(".")
        for dp, _, fs in os.walk(base):
            for fn in fs:
                fp = os.path.join(dp, fn)
                try: data = open(fp,"rb").read()
                except OSError: continue
                if _is_binary(data): continue
                for i, line in enumerate(data.decode(errors="replace").splitlines(),1):
                    if q in line:
                        hits.append(f"{os.path.relpath(fp, base)}:{i}: {line.strip()}")
        return ToolResult(tool=self.name, status="success",
                          summary=f"{len(hits)} matches", detail_for_llm="\n".join(hits))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_file_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/tools tests/tools
git commit -m "feat: file tools (list/read/search/write) with binary skip + size limit"
```

---

## Milestone 2 — Governance (Main Contribution, split across 6 tasks)

> Governance is deliberately decomposed into separate files/tasks: decision types + engine (T10), path fence (T11), dispatch integration (T12), command lexer (T13), command rules (T14), approval state machine (T15). **There is no single `guardrail.py`.**

### Task 10: Decision types + ordered PolicyEngine (first-match-wins) ✅ DONE (5a6739d, +3c402ea)

**Files:**
- Create: `aegiscode/governance/__init__.py`, `aegiscode/governance/decision.py`, `aegiscode/governance/engine.py`, `tests/governance/test_engine.py`

**Interfaces:**
- Consumes: `Action`, `Decision` (the canonical enum defined in Task 2 `aegiscode/config/schema.py`).
- Produces: `aegiscode/governance/decision.py` **re-exports** the canonical `Decision` (single source of truth is `config/schema.py`, created earlier in Task 2) so governance code can `from aegiscode.governance.decision import Decision`; `@dataclass PolicyRule(rule_id:str, matcher:Callable[[Action,ctx],bool], decision:Decision, reason:str)`; `@dataclass GovernanceVerdict(decision, rule_id, reason)`; `class PolicyEngine(rules:list[PolicyRule], default_fn:Callable)` with `evaluate(action, ctx)->GovernanceVerdict` (first matching rule wins; else `default_fn`).

- [ ] **Step 1: Write the failing test**
```python
# tests/governance/test_engine.py
from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import PolicyEngine, PolicyRule, GovernanceVerdict
from aegiscode.protocol.action import Action

def _deny_rm(a, ctx): return a.tool == "run_command" and "rm" in a.arguments.get("command","")

def test_first_match_wins():
    rules = [PolicyRule("R-RM", _deny_rm, Decision.DENY, "no rm")]
    eng = PolicyEngine(rules, default_fn=lambda a,c: GovernanceVerdict(Decision.ALLOW,"DEFAULT","ok"))
    v = eng.evaluate(Action(tool="run_command", arguments={"command":"rm -rf /"}), None)
    assert v.decision == Decision.DENY and v.rule_id == "R-RM"

def test_falls_through_to_default():
    eng = PolicyEngine([], default_fn=lambda a,c: GovernanceVerdict(Decision.ALLOW,"DEFAULT","ok"))
    v = eng.evaluate(Action(tool="read_file", arguments={"path":"a"}), None)
    assert v.decision == Decision.ALLOW and v.rule_id == "DEFAULT"

def test_decision_is_canonical_config_enum():
    from aegiscode.config.schema import Decision as ConfigDecision
    assert Decision is ConfigDecision            # single source of truth
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/governance/test_engine.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/governance/decision.py
# Single source of truth is config.schema.Decision (created in Task 2); re-export here.
from aegiscode.config.schema import Decision

__all__ = ["Decision"]
```
```python
# aegiscode/governance/engine.py
from dataclasses import dataclass
from typing import Callable
from aegiscode.governance.decision import Decision

@dataclass
class GovernanceVerdict:
    decision: Decision; rule_id: str; reason: str

@dataclass
class PolicyRule:
    rule_id: str; matcher: Callable; decision: Decision; reason: str

class PolicyEngine:
    def __init__(self, rules, default_fn): self.rules, self.default_fn = rules, default_fn
    def evaluate(self, action, ctx) -> GovernanceVerdict:
        for r in self.rules:
            if r.matcher(action, ctx):
                return GovernanceVerdict(r.decision, r.rule_id, r.reason)
        return self.default_fn(action, ctx)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/governance/test_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/governance tests/governance
git commit -m "feat: governance Decision enum + ordered first-match PolicyEngine"
```

---

### Task 11: Path fence (乙) — realpath ownership + sensitive-file blacklist ✅ DONE (fd91949, +1cde65e)

**Files:**
- Create: `aegiscode/governance/path_fence.py`, `tests/governance/test_path_fence.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `class PathVerdict(NamedTuple: allowed:bool, reason:str)`; `check_path(path:str, workspace_root:str, sensitive_patterns:list[str]) -> PathVerdict`. Algorithm: reject empty; join relative to root (absolute allowed only if inside); for existing target realpath it, for new file realpath its **parent** + verify the filename is not itself a symlink; require `os.path.realpath(target)` under `os.path.realpath(root)`; match sensitive patterns → deny. Linux semantics only.

- [ ] **Step 1: Write the failing test**
```python
# tests/governance/test_path_fence.py
import os
from aegiscode.governance.path_fence import check_path

def test_symlink_escape_denied(tmp_path):
    root = tmp_path / "ws"; root.mkdir()
    (root / "evil").symlink_to("/etc/passwd")
    assert check_path("evil", str(root), []).allowed is False

def test_parent_traversal_denied(tmp_path):
    root = tmp_path / "ws"; root.mkdir()
    assert check_path("../../etc/passwd", str(root), []).allowed is False

def test_new_file_in_workspace_allowed(tmp_path):
    root = tmp_path / "ws"; root.mkdir()
    assert check_path("src/new.py", str(root), []).allowed is True

def test_sensitive_file_denied(tmp_path):
    root = tmp_path / "ws"; root.mkdir(); (root/".env").write_text("K=v")
    assert check_path(".env", str(root), [".env","*.pem"]).allowed is False

def test_absolute_inside_allowed(tmp_path):
    root = tmp_path / "ws"; root.mkdir(); (root/"a.py").write_text("x")
    assert check_path(str(root/"a.py"), str(root), []).allowed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/governance/test_path_fence.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/governance/path_fence.py
import os, fnmatch
from typing import NamedTuple

class PathVerdict(NamedTuple):
    allowed: bool; reason: str

def check_path(path, workspace_root, sensitive_patterns) -> PathVerdict:
    if not path or not isinstance(path, str):
        return PathVerdict(False, "empty or non-string path")
    root = os.path.realpath(workspace_root)
    joined = path if os.path.isabs(path) else os.path.join(root, path)
    if os.path.islink(joined) or os.path.exists(joined):
        real = os.path.realpath(joined)
    else:                                        # new file: fence the parent
        parent = os.path.realpath(os.path.dirname(joined))
        if os.path.commonpath([parent, root]) != root:
            return PathVerdict(False, "parent dir outside workspace")
        real = os.path.join(parent, os.path.basename(joined))
    if os.path.commonpath([os.path.realpath(real), root]) != root:
        return PathVerdict(False, "path escapes workspace (traversal/symlink)")
    base = os.path.basename(path)
    for pat in sensitive_patterns:
        if fnmatch.fnmatch(base, pat) or pat.rstrip("/") in path.split(os.sep):
            return PathVerdict(False, f"sensitive file blocked: {pat}")
    return PathVerdict(True, "ok")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/governance/test_path_fence.py -v`
Expected: PASS (demo ③ backing test)

- [ ] **Step 5: Commit**
```bash
git add aegiscode/governance/path_fence.py tests/governance/test_path_fence.py
git commit -m "feat: path fence with realpath ownership + symlink-escape denial"
```

---

### Task 12: Governed dispatcher — wire path fence + default tiers into tool dispatch ✅ DONE (c62f0e0, +e752c54)

**Files:**
- Create: `aegiscode/governance/dispatcher.py`, `tests/governance/test_dispatcher.py`

**Interfaces:**
- Consumes: `ToolRegistry`, `PolicyEngine`, `check_path`, `Decision`, `ToolResult`.
- Produces: `class Dispatcher(registry, engine, path_config)` with `dispatch(action, ctx) -> tuple[GovernanceVerdict, ToolResult|None]`. Flow: unknown tool → `ToolResult(status="error", category="INVALID_ACTION")`, no exec; run path fence for file tools (fail → DENY verdict, `POLICY_DENIED`, no exec); else `engine.evaluate`; on DENY return verdict + `POLICY_DENIED` result, no exec; on REQUIRE_APPROVAL return verdict + None (loop handles pause); on ALLOW/ALLOW_WITH_AUDIT execute the tool. Default tiers: readonly→ALLOW, write→REQUIRE_APPROVAL (ALLOW if in `write_allowlist_dirs`), command not in allowlist→DENY.

- [ ] **Step 1: Write the failing test**
```python
# tests/governance/test_dispatcher.py
from types import SimpleNamespace
from aegiscode.governance.dispatcher import Dispatcher
from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import PolicyEngine, GovernanceVerdict
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.result import ToolResult
from aegiscode.protocol.action import Action

class OkTool:
    name = "read_file"
    def run(self, arguments, ctx): return ToolResult(tool="read_file", status="success", summary="ok")

def _disp(tmp_path, rules=None):
    reg = ToolRegistry(); reg.register(OkTool())
    eng = PolicyEngine(rules or [], default_fn=lambda a,c: GovernanceVerdict(Decision.ALLOW,"DEFAULT","ok"))
    return Dispatcher(reg, eng, path_config=SimpleNamespace(
        workspace_root=str(tmp_path), sensitive_patterns=[], readonly_tools={"read_file","list_files","search_text"}))

def test_unknown_tool_not_executed(tmp_path):
    d = _disp(tmp_path)
    verdict, result = d.dispatch(Action(tool="nope", arguments={}), SimpleNamespace())
    assert result.category == "INVALID_ACTION"

def test_path_escape_denied_before_exec(tmp_path):
    d = _disp(tmp_path)
    v, r = d.dispatch(Action(tool="read_file", arguments={"path":"../../etc/passwd"}),
                      SimpleNamespace(resolve=lambda p: p))
    assert v.decision == Decision.DENY and r.category == "POLICY_DENIED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/governance/test_dispatcher.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/governance/dispatcher.py
from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import GovernanceVerdict
from aegiscode.governance.path_fence import check_path
from aegiscode.tools.result import ToolResult

_FILE_TOOLS = {"read_file","write_file","list_files","search_text"}

class Dispatcher:
    def __init__(self, registry, engine, path_config):
        self.registry, self.engine, self.pc = registry, engine, path_config
    def dispatch(self, action, ctx):
        tool = self.registry.get(action.tool)
        if tool is None:
            return (GovernanceVerdict(Decision.DENY,"UNKNOWN_TOOL","unknown tool"),
                    ToolResult(tool=action.tool, status="error", category="INVALID_ACTION",
                               summary=f"unknown tool {action.tool}"))
        if action.tool in _FILE_TOOLS and "path" in action.arguments:
            pv = check_path(action.arguments["path"], self.pc.workspace_root, self.pc.sensitive_patterns)
            if not pv.allowed:
                return (GovernanceVerdict(Decision.DENY,"PATH_FENCE",pv.reason),
                        ToolResult(tool=action.tool, status="denied", category="POLICY_DENIED",
                                   summary=pv.reason))
        verdict = self.engine.evaluate(action, ctx)
        if verdict.decision == Decision.DENY:
            return (verdict, ToolResult(tool=action.tool, status="denied",
                    category="POLICY_DENIED", summary=verdict.reason))
        if verdict.decision == Decision.REQUIRE_APPROVAL:
            return (verdict, None)
        return (verdict, tool.run(action.arguments, ctx))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/governance/test_dispatcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/governance/dispatcher.py tests/governance/test_dispatcher.py
git commit -m "feat: governed dispatcher (path fence + tiers + no-exec on DENY/APPROVAL)"
```

---

### Task 13: Command lexer + structure-safety layer (甲, layers 1–2) ✅ DONE (9f1b33c, fix 40bc08c)

**Files:**
- Create: `aegiscode/governance/command_lexer.py`, `tests/governance/test_command_lexer.py`

**Interfaces:**
- Consumes: nothing (`shlex`).
- Produces: `class LexResult(NamedTuple: ok:bool, argv:list[str], reason:str, has_metastructure:bool)`; `lex_command(command:str) -> LexResult`. Detects pipes/redirects/chaining/command-substitution/subshell/background/glob-injection via raw-string scan + shlex; any metastructure → `ok=False, has_metastructure=True`. shlex failure → `ok=False`.

- [ ] **Step 1: Write the failing test**
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/governance/test_command_lexer.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/governance/command_lexer.py
import shlex
from typing import NamedTuple

class LexResult(NamedTuple):
    ok: bool; argv: list; reason: str; has_metastructure: bool

_META = ["|", ">", "<", ";", "&&", "||", "$(", "`", "&", "$(", "(", ")"]

def lex_command(command: str) -> LexResult:
    for token in _META:
        if token in command:
            return LexResult(False, [], f"shell metastructure {token!r} not allowed", True)
    try:
        argv = shlex.split(command)
    except ValueError as e:
        return LexResult(False, [], f"lex error: {e}", False)
    if not argv:
        return LexResult(False, [], "empty command", False)
    return LexResult(True, argv, "ok", False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/governance/test_command_lexer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/governance/command_lexer.py tests/governance/test_command_lexer.py
git commit -m "feat: command lexer + structure-safety layer (metastructure -> reject)"
```

---

### Task 14: Command allowlist + dangerous-param rules (甲, layers 3–4) ✅ DONE (85a1905, +839ceac)

**Files:**
- Create: `aegiscode/governance/command_rules.py`, `tests/governance/test_command_rules.py`

**Interfaces:**
- Consumes: `lex_command`, `Decision`.
- Produces: `judge_command(command:str, allowlist:list[str], rules:list[dict]) -> GovernanceVerdict`. Order: lex (metastructure/lex-fail → DENY); argv[0] not in allowlist → DENY; then param rules (flat `{argv0:str, args_contain:list[str], decision}` first-match); else ALLOW. `rules` is a list of **plain dicts** matching the `CommandRule` schema (Task 2); the caller wires `[r.model_dump() for r in config.governance.command_rules]`. `argv0` is a scalar string (never a list) — consistent with SPEC §11 M11. The dangerous set `sudo/su/rm/chmod/chown/curl/wget` is **not** listed as explicit rules; they fall through to DENY because they are absent from `command_allowlist`. Explicit rules cover `git push/reset --hard/clean` (DENY), `git commit` (APPROVAL), `pip install` (APPROVAL), `python -c` / `python -m` (DENY).

- [ ] **Step 1: Write the failing test**
```python
# tests/governance/test_command_rules.py
from aegiscode.governance.command_rules import judge_command
from aegiscode.governance.decision import Decision

ALLOW = ["python","pytest","git","pip","ls","cat"]
RULES = [
    {"argv0":"git","args_contain":["push"],"decision":"DENY"},
    {"argv0":"git","args_contain":["commit"],"decision":"REQUIRE_APPROVAL"},
    {"argv0":"pip","args_contain":["install"],"decision":"REQUIRE_APPROVAL"},
    {"argv0":"python","args_contain":["-c"],"decision":"DENY"},
    {"argv0":"python","args_contain":["-m"],"decision":"DENY"},
]

def test_rm_denied_by_metastructure_or_allowlist():
    assert judge_command("rm -rf /", ALLOW, RULES).decision == Decision.DENY

def test_pip_install_requires_approval():
    assert judge_command("pip install requests", ALLOW, RULES).decision == Decision.REQUIRE_APPROVAL

def test_python_dash_c_denied():
    assert judge_command("python -c \"import os\"", ALLOW, RULES).decision == Decision.DENY

def test_pytest_allowed():
    assert judge_command("pytest -q", ALLOW, RULES).decision == Decision.ALLOW

def test_not_in_allowlist_denied():
    assert judge_command("ncat 1.2.3.4 4444", ALLOW, RULES).decision == Decision.DENY

def test_pipe_denied():
    assert judge_command("cat x | sh", ALLOW, RULES).decision == Decision.DENY

def test_shipped_config_allows_pip_to_reach_approval():
    # Regression guard for the golden path, driven by the REAL schema defaults
    # (no hand-written mirror, no fallback). Because the dangerous-command rules are
    # baked into Governance defaults, code-only (no YAML) must already yield the
    # golden-path verdict. If someone empties the default rules or drops pip from the
    # allowlist, THIS test goes red.
    from aegiscode.config.schema import Governance
    g = Governance()                                          # code defaults only, no YAML
    assert "pip" in g.command_allowlist                       # else pip denied at allowlist layer
    assert len(g.command_rules) >= 5                          # rules are baked in, not empty
    rules = [r.model_dump() for r in g.command_rules]         # NO `or RULES` fallback
    assert judge_command("pip install requests",
                         g.command_allowlist, rules).decision == Decision.REQUIRE_APPROVAL
    # and a baked-in DENY still denies without any YAML:
    assert judge_command("git push origin main",
                         g.command_allowlist, rules).decision == Decision.DENY
```

Note: the dangerous-command rules ship in the `Governance` schema defaults (Task 2), so governance is secure-by-default with no `aegis.yaml`. A YAML `command_rules:` list fully replaces the default (declarative override). This test must run with **no** YAML loaded.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/governance/test_command_rules.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/governance/command_rules.py
from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import GovernanceVerdict
from aegiscode.governance.command_lexer import lex_command

def judge_command(command, allowlist, rules) -> GovernanceVerdict:
    lr = lex_command(command)
    if not lr.ok:
        return GovernanceVerdict(Decision.DENY, "CMD_STRUCT", lr.reason)
    argv0, args = lr.argv[0], lr.argv[1:]
    if argv0 not in allowlist:
        return GovernanceVerdict(Decision.DENY, "CMD_ALLOWLIST", f"{argv0} not in allowlist")
    for i, rule in enumerate(rules):
        if rule["argv0"] == argv0 and all(tok in args for tok in rule["args_contain"]):
            dec = Decision(rule["decision"])
            return GovernanceVerdict(dec, f"CMD_RULE_{i}", f"rule matched: {argv0} {rule['args_contain']}")
    return GovernanceVerdict(Decision.ALLOW, "CMD_DEFAULT_ALLOWED", f"{argv0} allowed")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/governance/test_command_rules.py -v`
Expected: PASS (demo ① backing test)

- [ ] **Step 5: Commit**
```bash
git add aegiscode/governance/command_rules.py tests/governance/test_command_rules.py
git commit -m "feat: command allowlist + dangerous-param rules (rm/sudo/pip/python -c)"
```

---

### Task 15: Approval state machine (HITL) ✅ DONE (cedc259, +85f9ad3)

**Files:**
- Create: `aegiscode/governance/approval.py`, `tests/governance/test_approval.py`

**Interfaces:**
- Consumes: `Action`.
- Produces: `class ApprovalState(str,Enum)` PENDING/APPROVED/REJECTED/EXPIRED/SUPERSEDED; `fingerprint(action)->str` (sha256 of canonical tool+sorted args); `@dataclass ApprovalRequest(approval_id, task_id, step_index, action_snapshot:dict, action_fingerprint, rule_id, reason, risk_explanation, state)`; `class ApprovalStore` with `create(...)`, `decide(approval_id, approved:bool)`, `check_remembered(task_id, fp)->bool`, `remember(task_id, fp)`; and `validate_resume(approved_fp: str, current_action)` → raises `SupersededError` if `fingerprint(current_action) != approved_fp`.

- [ ] **Step 1: Write the failing test**
```python
# tests/governance/test_approval.py
import pytest
from aegiscode.governance.approval import (ApprovalStore, ApprovalState, fingerprint,
                                           validate_resume, SupersededError)
from aegiscode.protocol.action import Action

def test_fingerprint_stable_and_sensitive():
    a1 = Action(tool="run_command", arguments={"command":"pip install x"})
    a2 = Action(tool="run_command", arguments={"command":"pip install y"})
    assert fingerprint(a1) == fingerprint(a1)
    assert fingerprint(a1) != fingerprint(a2)

def test_decide_transitions():
    s = ApprovalStore()
    req = s.create("t1", 2, {"tool":"x"}, "fp", "R", "reason", "risk")
    s.decide(req.approval_id, True)
    assert s.get(req.approval_id).state == ApprovalState.APPROVED

def test_superseded_when_action_changes():
    a1 = Action(tool="run_command", arguments={"command":"pip install x"})
    a2 = Action(tool="run_command", arguments={"command":"pip install evil"})
    with pytest.raises(SupersededError):
        validate_resume(fingerprint(a1), a2)

def test_remember_same_fingerprint():
    s = ApprovalStore(); s.remember("t1","fp1")
    assert s.check_remembered("t1","fp1") is True
    assert s.check_remembered("t1","other") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/governance/test_approval.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/governance/approval.py
import hashlib, json, uuid
from dataclasses import dataclass, field
from enum import Enum

class ApprovalState(str, Enum):
    PENDING="PENDING"; APPROVED="APPROVED"; REJECTED="REJECTED"
    EXPIRED="EXPIRED"; SUPERSEDED="SUPERSEDED"

class SupersededError(RuntimeError): ...

def fingerprint(action) -> str:
    canon = json.dumps({"tool":action.tool,"arguments":action.arguments}, sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()

def validate_resume(approved_fp: str, current_action) -> None:
    if fingerprint(current_action) != approved_fp:
        raise SupersededError("action changed since approval")

@dataclass
class ApprovalRequest:
    approval_id: str; task_id: str; step_index: int; action_snapshot: dict
    action_fingerprint: str; rule_id: str; reason: str; risk_explanation: str
    state: ApprovalState = ApprovalState.PENDING

class ApprovalStore:
    def __init__(self):
        self._reqs = {}; self._remembered = set()
    def create(self, task_id, step_index, snapshot, fp, rule_id, reason, risk):
        req = ApprovalRequest(str(uuid.uuid4()), task_id, step_index, snapshot, fp, rule_id, reason, risk)
        self._reqs[req.approval_id] = req; return req
    def get(self, approval_id): return self._reqs[approval_id]
    def decide(self, approval_id, approved: bool):
        self._reqs[approval_id].state = ApprovalState.APPROVED if approved else ApprovalState.REJECTED
    def remember(self, task_id, fp): self._remembered.add((task_id, fp))
    def check_remembered(self, task_id, fp): return (task_id, fp) in self._remembered
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/governance/test_approval.py -v`
Expected: PASS (demo ④ backing test)

- [ ] **Step 5: Commit**
```bash
git add aegiscode/governance/approval.py tests/governance/test_approval.py
git commit -m "feat: HITL approval state machine + fingerprint supersede + remember"
```

---

### Task 16: run_command executor tool (甲 layer 5, shell=False) ✅ DONE (b64465b)

**Files:**
- Create: `aegiscode/tools/command_tool.py`, `tests/tools/test_command_tool.py`

**Interfaces:**
- Consumes: `judge_command`, `Decision`, `lex_command`, `ToolResult`.
- Produces: `RunCommandTool(allowlist, rules, timeout_sec, output_max_bytes)`; `run(arguments, ctx)` runs the already-approved argv via `subprocess.run(argv, shell=False, cwd=ctx.workspace_root, timeout=...)`, captures stdout/stderr truncated to `output_max_bytes`, maps timeout→`TIMEOUT`, non-zero→`status="failure"`. (Governance judgement itself is done by the dispatcher via `judge_command`; this tool only executes what was allowed.)

- [ ] **Step 1: Write the failing test**
```python
# tests/tools/test_command_tool.py
from types import SimpleNamespace
from aegiscode.tools.command_tool import RunCommandTool

def _ctx(tmp_path): return SimpleNamespace(workspace_root=str(tmp_path))

def test_runs_echo(tmp_path):
    r = RunCommandTool(["echo"], [], 5, 65536).run({"command":"echo hello"}, _ctx(tmp_path))
    assert r.status == "success" and "hello" in r.detail_for_llm

def test_nonzero_exit_is_failure(tmp_path):
    r = RunCommandTool(["python"], [], 5, 65536).run(
        {"command":"python -c \"import sys;sys.exit(3)\""}, _ctx(tmp_path))
    # note: this tool executes argv directly; governance would have blocked python -c upstream.
    assert r.exit_code == 3 and r.status == "failure"

def test_timeout_maps_to_timeout(tmp_path):
    r = RunCommandTool(["python"], [], 1, 65536).run(
        {"command":"python -c \"import time;time.sleep(5)\""}, _ctx(tmp_path))
    assert r.category == "TIMEOUT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_command_tool.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/tools/command_tool.py
import subprocess, shlex
from aegiscode.tools.result import ToolResult

class RunCommandTool:
    name = "run_command"
    def __init__(self, allowlist, rules, timeout_sec, output_max_bytes):
        self.allowlist, self.rules = allowlist, rules
        self.timeout, self.max_bytes = timeout_sec, output_max_bytes
    def run(self, arguments, ctx):
        argv = shlex.split(arguments["command"])
        try:
            p = subprocess.run(argv, shell=False, cwd=ctx.workspace_root,
                               capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return ToolResult(tool=self.name, status="failure", category="TIMEOUT",
                              summary="command timed out")
        out = (p.stdout + p.stderr)[: self.max_bytes]
        truncated = len(p.stdout + p.stderr) > self.max_bytes
        status = "success" if p.returncode == 0 else "failure"
        return ToolResult(tool=self.name, status=status,
                          category=None if status=="success" else "TOOL_ERROR",
                          summary=f"exit {p.returncode}", detail_for_llm=out,
                          exit_code=p.returncode, truncated=truncated)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_command_tool.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/tools/command_tool.py tests/tools/test_command_tool.py
git commit -m "feat: run_command executor (shell=False, argv, timeout, truncation)"
```

---

### Task 17: run_tests sensor + finish tool ✅ DONE (93d1ca7)

**Files:**
- Create: `aegiscode/tools/run_tests_tool.py`, `aegiscode/tools/finish_tool.py`, `tests/tools/test_run_tests.py`

**Interfaces:**
- Consumes: `RunCommandTool` pattern, `ToolResult`.
- Produces: `RunTestsTool(test_command, timeout, max_bytes)` executing the fixed configured `test_command` (ignores arbitrary args) and returning a raw `ToolResult` (classification is Task 18); `FinishTool` returning `ToolResult(tool="finish", status="success", summary="agent requested finish")` with `artifacts={"finish":True}`.

- [ ] **Step 1: Write the failing test**
```python
# tests/tools/test_run_tests.py
from types import SimpleNamespace
from aegiscode.tools.run_tests_tool import RunTestsTool
from aegiscode.tools.finish_tool import FinishTool

def test_runs_fixed_command(tmp_path):
    (tmp_path/"t_ok.py").write_text("def test_ok():\n    assert True\n")
    r = RunTestsTool("pytest -q", 30, 65536).run({}, SimpleNamespace(workspace_root=str(tmp_path)))
    assert r.exit_code == 0

def test_finish_flag():
    r = FinishTool().run({}, SimpleNamespace())
    assert r.artifacts.get("finish") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_run_tests.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/tools/run_tests_tool.py
import subprocess, shlex
from aegiscode.tools.result import ToolResult

class RunTestsTool:
    name = "run_tests"
    def __init__(self, test_command, timeout_sec, output_max_bytes):
        self.cmd, self.timeout, self.max_bytes = test_command, timeout_sec, output_max_bytes
    def run(self, arguments, ctx):
        try:
            p = subprocess.run(shlex.split(self.cmd), shell=False, cwd=ctx.workspace_root,
                               capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return ToolResult(tool=self.name, status="failure", category="TIMEOUT", summary="tests timed out")
        out = (p.stdout + p.stderr)[: self.max_bytes]
        return ToolResult(tool=self.name, status="success" if p.returncode==0 else "failure",
                          summary=f"tests exit {p.returncode}", detail_for_llm=out, exit_code=p.returncode)
```
```python
# aegiscode/tools/finish_tool.py
from aegiscode.tools.result import ToolResult
class FinishTool:
    name = "finish"
    def run(self, arguments, ctx):
        return ToolResult(tool="finish", status="success",
                          summary="agent requested finish", artifacts={"finish": True})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_run_tests.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/tools/run_tests_tool.py aegiscode/tools/finish_tool.py tests/tools/test_run_tests.py
git commit -m "feat: run_tests sensor (fixed command) + finish control tool"
```

---

## Milestone 3 — Feedback, Audit, Memory

### Task 18: Feedback classifier + pytest parser + no-progress fingerprint ✅ DONE (c0df597, +422f0f8)

**Files:**
- Create: `aegiscode/feedback/__init__.py`, `aegiscode/feedback/classifier.py`, `aegiscode/feedback/pytest_parser.py`, `tests/feedback/test_classifier.py`

**Interfaces:**
- Consumes: `ToolResult`, `redact`.
- Produces: `classify(tool_result) -> str` returning one of the 8 categories (TEST_FAILURE/TOOL_ERROR/POLICY_DENIED/APPROVAL_REJECTED/INVALID_ACTION/TIMEOUT/NO_PROGRESS/INTERNAL_ERROR); `summarize_pytest(raw:str) -> str` (failed test names + assertion lines + last 20 traceback lines); `class ProgressTracker(window=3)` with `seen(fingerprint)->bool` (True if exact fingerprint appears within last `window`).

- [ ] **Step 1: Write the failing test**
```python
# tests/feedback/test_classifier.py
from aegiscode.feedback.classifier import classify, ProgressTracker
from aegiscode.feedback.pytest_parser import summarize_pytest
from aegiscode.tools.result import ToolResult

def test_classify_test_failure():
    tr = ToolResult(tool="run_tests", status="failure", exit_code=1, summary="x")
    assert classify(tr) == "TEST_FAILURE"

def test_classify_policy_denied():
    tr = ToolResult(tool="run_command", status="denied", category="POLICY_DENIED", summary="x")
    assert classify(tr) == "POLICY_DENIED"

def test_summarize_pytest_keeps_failed_names():
    raw = "tests/test_a.py::test_x FAILED\n" + "trace\n"*50 + "E assert 1 == 2\n"
    out = summarize_pytest(raw)
    assert "test_x" in out and "assert 1 == 2" in out and len(out.splitlines()) < 40

def test_progress_tracker_detects_repeat():
    t = ProgressTracker(window=3)
    assert t.seen("fp") is False
    assert t.seen("fp") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/feedback/test_classifier.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/feedback/pytest_parser.py
def summarize_pytest(raw: str) -> str:
    lines = raw.splitlines()
    failed = [l for l in lines if "FAILED" in l or l.strip().startswith("E ")]
    tail = lines[-20:]
    return "\n".join(dict.fromkeys(failed + tail))
```
```python
# aegiscode/feedback/classifier.py
from collections import deque

def classify(tr) -> str:
    if tr.category in {"POLICY_DENIED","INVALID_ACTION","TIMEOUT","TOOL_ERROR",
                       "APPROVAL_REJECTED","INTERNAL_ERROR","NO_PROGRESS"}:
        return tr.category
    if tr.tool == "run_tests" and tr.status == "failure":
        return "TEST_FAILURE"
    if tr.status in {"failure","error"}:
        return "TOOL_ERROR"
    return None  # success → no failure category

class ProgressTracker:
    def __init__(self, window=3): self._recent = deque(maxlen=window)
    def seen(self, fp: str) -> bool:
        hit = fp in self._recent
        self._recent.append(fp)
        return hit
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/feedback/test_classifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/feedback tests/feedback
git commit -m "feat: feedback classifier + pytest summarizer + no-progress tracker"
```

---

### Task 19: Audit events + SHA256 hash chain + verify_chain ✅ DONE (af405cf, +8c36acb, +7f1477d)

**Files:**
- Create: `aegiscode/audit/__init__.py`, `aegiscode/audit/events.py`, `aegiscode/audit/chain.py`, `tests/audit/test_chain.py`

**Interfaces:**
- Consumes: `redact`, sqlite connection.
- Produces: `class EventType(str,Enum)` (7 types per SPEC §6 M8); `class AuditLog(conn)` with `append(task_id, step_index, event_type, payload:dict) -> str` (redacts payload, computes `hash=sha256(prev_hash + canonical_json)`, inserts) and `verify_chain(task_id) -> tuple[bool,int|None]` (recompute; return (True,None) or (False, first_bad_step)).

- [ ] **Step 1: Write the failing test**
```python
# tests/audit/test_chain.py
from aegiscode.persistence.db import open_db
from aegiscode.audit.chain import AuditLog
from aegiscode.audit.events import EventType

def test_chain_verifies(tmp_path):
    conn = open_db(str(tmp_path/"a.sqlite"))
    log = AuditLog(conn)
    for i in range(3):
        log.append("t1", i, EventType.TOOL_EXECUTED, {"i": i})
    assert log.verify_chain("t1") == (True, None)

def test_tamper_detected(tmp_path):
    conn = open_db(str(tmp_path/"a.sqlite"))
    log = AuditLog(conn); 
    for i in range(3): log.append("t1", i, EventType.TOOL_EXECUTED, {"i": i})
    conn.execute("UPDATE audit_events SET payload_json='{\"i\":99}' WHERE step_index=1")
    ok, bad = log.verify_chain("t1")
    assert ok is False and bad == 1

def test_payload_redacted(tmp_path):
    conn = open_db(str(tmp_path/"a.sqlite"))
    log = AuditLog(conn)
    log.append("t1", 0, EventType.TOOL_EXECUTED, {"out":"token=sk-abcdef1234567890abcdef1234567890"})
    row = conn.execute("SELECT payload_json FROM audit_events").fetchone()[0]
    assert "sk-abcdef" not in row
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/audit/test_chain.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/audit/events.py
from enum import Enum
class EventType(str, Enum):
    ACTION_PROPOSED="ACTION_PROPOSED"; GOVERNANCE_DECISION="GOVERNANCE_DECISION"
    APPROVAL_REQUESTED="APPROVAL_REQUESTED"; APPROVAL_DECIDED="APPROVAL_DECIDED"
    TOOL_EXECUTED="TOOL_EXECUTED"; FEEDBACK="FEEDBACK"; TERMINATION="TERMINATION"
```
```python
# aegiscode/audit/chain.py
import hashlib, json, datetime
from aegiscode.security.redactor import redact

GENESIS = "0" * 64

class AuditLog:
    def __init__(self, conn): self.conn = conn
    def _prev_hash(self, task_id):
        row = self.conn.execute(
            "SELECT hash FROM audit_events WHERE task_id=? ORDER BY event_id DESC LIMIT 1",
            (task_id,)).fetchone()
        return row[0] if row else GENESIS
    def append(self, task_id, step_index, event_type, payload: dict) -> str:
        payload_json = redact(json.dumps(payload, sort_keys=True))
        ts = datetime.datetime.utcnow().isoformat()
        prev = self._prev_hash(task_id)
        body = json.dumps({"task_id":task_id,"step_index":step_index,
            "event_type":str(event_type),"timestamp":ts,"payload_json":payload_json}, sort_keys=True)
        h = hashlib.sha256((prev + body).encode()).hexdigest()
        self.conn.execute(
            "INSERT INTO audit_events(task_id,step_index,timestamp,event_type,payload_json,prev_hash,hash)"
            " VALUES(?,?,?,?,?,?,?)", (task_id, step_index, ts, str(event_type), payload_json, prev, h))
        return h
    def verify_chain(self, task_id):
        prev = GENESIS
        for row in self.conn.execute(
            "SELECT step_index,timestamp,event_type,payload_json,prev_hash,hash "
            "FROM audit_events WHERE task_id=? ORDER BY event_id", (task_id,)):
            step_index, ts, et, pj, stored_prev, stored_hash = row
            body = json.dumps({"task_id":task_id,"step_index":step_index,
                "event_type":et,"timestamp":ts,"payload_json":pj}, sort_keys=True)
            h = hashlib.sha256((prev + body).encode()).hexdigest()
            if stored_prev != prev or stored_hash != h:
                return (False, step_index)
            prev = stored_hash
        return (True, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/audit/test_chain.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/audit tests/audit
git commit -m "feat: audit events + SHA256 hash chain + verify_chain tamper detection"
```

---

### Task 20: Memory store (write-with-redaction + filtered retrieval) ✅ DONE (738ad8a, +ce70499)

**Files:**
- Create: `aegiscode/memory/__init__.py`, `aegiscode/memory/store.py`, `tests/memory/test_store.py`

**Interfaces:**
- Consumes: sqlite connection, `redact`, secret patterns.
- Produces: `class MemoryStore(conn)` with `write(project_id, type, key, value, tags, source, confirmed=None) -> str|None` (returns None and refuses if value matches a secret pattern; `source='agent'` forces `confirmed=False`); `retrieve(project_id, query=None, top_k=8) -> list[dict]` (filter by project_id + optional keyword LIKE on key/value/tags, order by `last_used_at DESC`, limit top_k; bumps `use_count`/`last_used_at`); `is_governance_usable(row) -> bool` (False when `source='agent'` — agent memory never used as governance basis).

- [ ] **Step 1: Write the failing test**
```python
# tests/memory/test_store.py
from aegiscode.persistence.db import open_db
from aegiscode.memory.store import MemoryStore

def _store(tmp_path): return MemoryStore(open_db(str(tmp_path/"m.sqlite")))

def test_refuses_secret_value(tmp_path):
    s = _store(tmp_path)
    mid = s.write("p1","PROJECT_CONVENTION","k","token=sk-abcdef1234567890abcdef1234567890",[],"user")
    assert mid is None

def test_write_and_retrieve_by_keyword(tmp_path):
    s = _store(tmp_path)
    s.write("p1","PROJECT_CONVENTION","style","use 4-space indent",["style"],"user")
    hits = s.retrieve("p1", query="indent", top_k=8)
    assert hits and "indent" in hits[0]["value"]

def test_agent_memory_not_governance_usable(tmp_path):
    s = _store(tmp_path)
    s.write("p1","DECISION","guess","maybe use redis",[],"agent")
    row = s.retrieve("p1", query="redis")[0]
    assert row["source"] == "agent" and row["confirmed"] == 0
    assert s.is_governance_usable(row) is False

def test_topk_limit(tmp_path):
    s = _store(tmp_path)
    for i in range(12): s.write("p1","CODEBASE_FACT",f"k{i}",f"v{i}",[],"system")
    assert len(s.retrieve("p1", top_k=8)) == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/memory/test_store.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/memory/store.py
import uuid, json, datetime
from aegiscode.credentials.scanner import scan_text

class MemoryStore:
    def __init__(self, conn): self.conn = conn
    def write(self, project_id, type, key, value, tags, source, confirmed=None):
        if scan_text(value):                      # refuse secrets
            return None
        if source == "agent":
            confirmed = False
        elif confirmed is None:
            confirmed = True
        mid, now = str(uuid.uuid4()), datetime.datetime.utcnow().isoformat()
        self.conn.execute(
            "INSERT INTO memories(memory_id,project_id,type,key,value,tags_json,source,"
            "confirmed,created_at,last_used_at,use_count) VALUES(?,?,?,?,?,?,?,?,?,?,0)",
            (mid, project_id, type, key, value, json.dumps(tags), source,
             1 if confirmed else 0, now, now))
        return mid
    def retrieve(self, project_id, query=None, top_k=8):
        sql = "SELECT memory_id,project_id,type,key,value,tags_json,source,confirmed,use_count " \
              "FROM memories WHERE project_id=?"
        params = [project_id]
        if query:
            sql += " AND (key LIKE ? OR value LIKE ? OR tags_json LIKE ?)"
            params += [f"%{query}%"]*3
        sql += " ORDER BY last_used_at DESC LIMIT ?"; params.append(top_k)
        cols = ["memory_id","project_id","type","key","value","tags_json","source","confirmed","use_count"]
        rows = [dict(zip(cols, r)) for r in self.conn.execute(sql, params)]
        now = datetime.datetime.utcnow().isoformat()
        for r in rows:
            self.conn.execute("UPDATE memories SET use_count=use_count+1,last_used_at=? WHERE memory_id=?",
                              (now, r["memory_id"]))
        return rows
    @staticmethod
    def is_governance_usable(row) -> bool:
        return row["source"] != "agent"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/memory/test_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/memory/store.py tests/memory/test_store.py
git commit -m "feat: memory store (secret-refusing write, filtered retrieval, agent non-governance)"
```

---

### Task 21: Context builder (6-tier budget + deterministic summarize) ✅ DONE (932e893, +b633118); M3 final-review fixes in e529ea8

**Files:**
- Create: `aegiscode/memory/context_builder.py`, `tests/memory/test_context_builder.py`

**Interfaces:**
- Consumes: `MemoryStore`, `AegisConfig`.
- Produces: `build_context(system_prompt, tool_protocol, task, recent_steps:list[dict], last_feedback, memories:list[dict], budget_chars) -> list[dict]` — assembles messages in priority order (1 system+protocol 2 task 3 task-state+recent N 4 last feedback 5 memories top-k 6 code snippets); when total chars exceed `budget_chars`, **deterministically summarize the oldest recent step** via `summarize_step(step) -> str` (keep tool + decision + feedback category, drop detail) — never calls an LLM.

- [ ] **Step 1: Write the failing test**
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/memory/test_context_builder.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/memory/context_builder.py
def summarize_step(step) -> str:
    return (f"[step tool={step.get('tool')} "
            f"decision={step.get('governance_decision')} "
            f"feedback={step.get('feedback_category')}]")

def _len(msgs): return sum(len(m["content"]) for m in msgs)

def build_context(system_prompt, tool_protocol, task, recent_steps,
                  last_feedback, memories, budget_chars):
    head = [{"role":"system","content": system_prompt + "\n" + tool_protocol},
            {"role":"user","content": f"TASK: {task}"}]
    mem_txt = "\n".join(f"- {m['key']}: {m['value']}" for m in memories)
    tail = []
    if mem_txt: tail.append({"role":"system","content": "MEMORY:\n"+mem_txt})
    if last_feedback: tail.append({"role":"user","content": "FEEDBACK:\n"+last_feedback})
    # recent steps newest-last; summarize oldest first when over budget
    detailed = [{"role":"assistant","content":
                 f"step {i}: {s.get('tool')} -> {s.get('feedback_category')}\n{s.get('detail','')}"}
                for i, s in enumerate(recent_steps)]
    msgs = head + detailed + tail
    idx = 0
    while _len(msgs) > budget_chars and idx < len(detailed):
        detailed[idx] = {"role":"assistant","content": summarize_step(recent_steps[idx])}
        msgs = head + detailed + tail
        idx += 1
    return msgs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/memory/test_context_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/memory/context_builder.py tests/memory/test_context_builder.py
git commit -m "feat: context builder (6-tier budget + deterministic oldest-step summarize)"
```

---

### Task 22: Termination reasons + priority decision

**Files:**
- Create: `aegiscode/loop/__init__.py`, `aegiscode/loop/termination.py`, `tests/loop/test_termination.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `class TerminationReason(str,Enum)` (9 values per SPEC §6 M1); `@dataclass LoopCounters(step, consecutive_failures, invalid_actions, no_progress_hits)`; `decide_termination(c:LoopCounters, limits:dict) -> TerminationReason|None` (returns a counting-tier reason when a limit is hit, else None). COMPLETED/FINISH_REJECTED/LLM_ERROR/INTERNAL_ERROR/CANCELLED are set by the loop directly, not here.

- [ ] **Step 1: Write the failing test**
```python
# tests/loop/test_termination.py
from aegiscode.loop.termination import decide_termination, LoopCounters, TerminationReason

LIM = {"max_steps":25,"max_consecutive_failures":5,"no_progress_repeat_limit":3,"action_retry_limit":3}

def test_none_when_healthy():
    assert decide_termination(LoopCounters(1,0,0,0), LIM) is None

def test_max_steps():
    assert decide_termination(LoopCounters(25,0,0,0), LIM) == TerminationReason.MAX_STEPS

def test_consecutive_failures():
    assert decide_termination(LoopCounters(3,5,0,0), LIM) == TerminationReason.CONSECUTIVE_FAILURES

def test_no_progress():
    assert decide_termination(LoopCounters(3,0,0,3), LIM) == TerminationReason.NO_PROGRESS

def test_invalid_action_limit():
    assert decide_termination(LoopCounters(3,0,3,0), LIM) == TerminationReason.INVALID_ACTION_LIMIT

def test_nine_reasons_defined():
    assert len(list(TerminationReason)) == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loop/test_termination.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/loop/termination.py
from dataclasses import dataclass
from enum import Enum

class TerminationReason(str, Enum):
    COMPLETED="COMPLETED"; FINISH_REJECTED="FINISH_REJECTED"; MAX_STEPS="MAX_STEPS"
    CONSECUTIVE_FAILURES="CONSECUTIVE_FAILURES"; NO_PROGRESS="NO_PROGRESS"
    INVALID_ACTION_LIMIT="INVALID_ACTION_LIMIT"; LLM_ERROR="LLM_ERROR"
    INTERNAL_ERROR="INTERNAL_ERROR"; CANCELLED="CANCELLED"

@dataclass
class LoopCounters:
    step: int; consecutive_failures: int; invalid_actions: int; no_progress_hits: int

def decide_termination(c: LoopCounters, limits: dict):
    if c.invalid_actions >= limits["action_retry_limit"]:
        return TerminationReason.INVALID_ACTION_LIMIT
    if c.consecutive_failures >= limits["max_consecutive_failures"]:
        return TerminationReason.CONSECUTIVE_FAILURES
    if c.no_progress_hits >= limits["no_progress_repeat_limit"]:
        return TerminationReason.NO_PROGRESS
    if c.step >= limits["max_steps"]:
        return TerminationReason.MAX_STEPS
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loop/test_termination.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/loop/termination.py tests/loop/test_termination.py
git commit -m "feat: termination reasons (9) + counting-tier decide_termination"
```

---

## Milestone 4 — Core loop

### Task 23: HarnessCore main loop (integration)

**Files:**
- Create: `aegiscode/loop/harness.py`, `tests/loop/test_harness.py`, **`tests/helpers.py`** (the shared test factory; Step 1 imports `make_harness` from it, and Tasks 26/27 later extend it with `make_service`/`make_api_client`)

**Interfaces:**
- Consumes: `LLMClient`, `parse_action`/`ActionParseError`, `Dispatcher`, `PolicyEngine`, `judge_command`, `classify`, `ProgressTracker`, `fingerprint`, `AuditLog`, `build_context`, `decide_termination`, `LoopCounters`, `TerminationReason`, `RunTestsTool`.
- Produces: `class HarnessCore(llm, dispatcher, audit, config, ctx, final_verifier)` with `run(task_description) -> TerminationReason`. Per-turn order (SPEC §6 M1 priority): build context → `llm.complete` (retry 3 → LLM_ERROR) → `parse_action` (fail → INVALID_ACTION feedback, count; 3 → INVALID_ACTION_LIMIT) → audit ACTION_PROPOSED → `dispatcher.dispatch` → on REQUIRE_APPROVAL raise pause/await decision (here: injected `approval_resolver`) → on DENY feedback POLICY_DENIED (+failure count, no stop) → execute, classify feedback → if action is `finish`, run `final_verifier()`; pass→COMPLETED else FINISH_REJECTED feedback → check `decide_termination`. `final_verifier` re-runs target tests independently; COMPLETED only if it passes.

- [ ] **Step 1: Write the failing test** (the two core demos, MockLLM-driven)
```python
# tests/loop/test_harness.py
from tests.helpers import make_harness   # small factory wiring real components + MockLLM
from aegiscode.loop.termination import TerminationReason

def test_demo1_dangerous_command_denied(tmp_path):
    # MockLLM asks to run "rm -rf /" then finish
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"run_command","arguments":{"command":"rm -rf /"}}',
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True)
    h.run("do something")
    assert spy.command_executions == 0                 # never executed
    assert any(e["event_type"]=="GOVERNANCE_DECISION" and e["decision"]=="DENY"
               for e in spy.audit_events)

def test_demo2_failure_feedback_changes_action(tmp_path):
    # round1 write bad, round2 run_tests (fail), round3 write different, round4 run_tests (pass), round5 finish
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"write_file","arguments":{"path":"src/m.py","content":"def f():\\n    return 0\\n"}}',
        '{"tool":"run_tests","arguments":{}}',
        '{"tool":"write_file","arguments":{"path":"src/m.py","content":"def f():\\n    return 1\\n"}}',
        '{"tool":"run_tests","arguments":{}}',
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True, fail_first_test=True)
    reason = h.run("fix f")
    # feedback from round2 must appear in round3's messages
    assert any("TEST_FAILURE" in m or "fail" in m.lower() for m in spy.messages_at_round(3))
    assert spy.action_at(3) != spy.action_at(1)        # action changed
    assert reason == TerminationReason.COMPLETED        # decided by final_verifier, not MockLLM
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loop/test_harness.py -v`
Expected: FAIL — `aegiscode.loop.harness` / `tests.helpers` not found.

- [ ] **Step 3: Write minimal implementation** (create `tests/helpers.py` factory + `harness.py`)

`harness.py` core skeleton (compose prior units; full body in this task):
```python
# aegiscode/loop/harness.py  (essential control flow)
from aegiscode.protocol.parser import parse_action, ActionParseError
from aegiscode.governance.decision import Decision
from aegiscode.feedback.classifier import classify, ProgressTracker
from aegiscode.governance.approval import fingerprint
from aegiscode.audit.events import EventType
from aegiscode.loop.termination import decide_termination, LoopCounters, TerminationReason

class HarnessCore:
    def __init__(self, llm, dispatcher, audit, config, ctx, final_verifier, approval_resolver=None):
        self.llm, self.dispatcher, self.audit = llm, dispatcher, audit
        self.config, self.ctx, self.final_verifier = config, ctx, final_verifier
        self.approval_resolver = approval_resolver
        self.progress = ProgressTracker(config.limits.no_progress_repeat_limit)

    def run(self, task_description) -> TerminationReason:
        c = LoopCounters(0, 0, 0, 0); last_feedback = ""
        while True:
            reason = decide_termination(c, self.config.limits.model_dump())
            if reason: self._audit_term(reason); return reason
            messages = self._build(task_description, last_feedback)
            try:
                text = self._complete_with_retry(messages)
            except Exception:
                self._audit_term(TerminationReason.LLM_ERROR); return TerminationReason.LLM_ERROR
            try:
                action = parse_action(text)
            except ActionParseError as e:
                c.invalid_actions += 1; last_feedback = f"INVALID_ACTION: {e}"; continue
            c.invalid_actions = 0
            self.audit.append(self.ctx.task_id, c.step, EventType.ACTION_PROPOSED,
                              {"tool": action.tool, "arguments": action.arguments})
            if self.progress.seen(fingerprint(action)):
                c.no_progress_hits += 1; last_feedback = "NO_PROGRESS: repeated action"; continue
            verdict, result = self.dispatcher.dispatch(action, self.ctx)
            self.audit.append(self.ctx.task_id, c.step, EventType.GOVERNANCE_DECISION,
                              {"decision": verdict.decision.value, "rule_id": verdict.rule_id})
            if verdict.decision == Decision.REQUIRE_APPROVAL:
                approved = self.approval_resolver(action, verdict) if self.approval_resolver else False
                if not approved:
                    c.consecutive_failures += 1
                    last_feedback = f"APPROVAL_REJECTED: {verdict.reason}"; c.step += 1; continue
                verdict2, result = self.dispatcher.execute_approved(action, self.ctx)
            if result is not None and action.tool == "finish":
                if self.final_verifier():
                    self._audit_term(TerminationReason.COMPLETED); return TerminationReason.COMPLETED
                last_feedback = "FINISH_REJECTED: final verification failed"; c.step += 1; continue
            cat = classify(result) if result else "POLICY_DENIED"
            if cat: c.consecutive_failures += 1
            else: c.consecutive_failures = 0
            last_feedback = f"{cat or 'OK'}: {result.summary if result else ''}\n{result.detail_for_llm if result else ''}"
            self.audit.append(self.ctx.task_id, c.step, EventType.FEEDBACK, {"category": cat})
            c.step += 1
```
(Also add `Dispatcher.execute_approved(action, ctx)` that runs the tool bypassing the REQUIRE_APPROVAL gate; and write `tests/helpers.py` `make_harness` wiring MockLLM + real governance + a spy audit/ctx + a `final_verifier` that returns `final_ok` and, when `fail_first_test`, makes the first `run_tests` fail.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loop/test_harness.py -v`
Expected: PASS (demos ① and ② green)

- [ ] **Step 5: Commit**
```bash
git add aegiscode/loop/harness.py aegiscode/governance/dispatcher.py tests/loop/test_harness.py tests/helpers.py
git commit -m "feat: HarnessCore main loop wiring governance+feedback+audit+termination"
```

---

## Milestone 5 — Credentials

### Task 24: Credential store (keyring → .env → env, fail-safe)

**Files:**
- Create: `aegiscode/credentials/__init__.py`, `aegiscode/credentials/store.py`, `tests/credentials/test_store.py`

**Interfaces:**
- Consumes: `keyring` (injectable backend for tests).
- Produces: `class CredentialStore(backend, allow_dotenv=False, env=None, dotenv_path=None)` with `set_key(value)` (via backend), `status() -> dict` (`{"configured":bool, "masked":"sk-…abcd"|None}` — never plaintext), `clear()`, `get_key() -> str|None` (read order keyring→.env if allow_dotenv→env). `.env` disabled unless `allow_dotenv=True`.

- [ ] **Step 1: Write the failing test**
```python
# tests/credentials/test_store.py
from aegiscode.credentials.store import CredentialStore

class FakeBackend:
    def __init__(self): self.v = None
    def set_password(self, s, u, v): self.v = v
    def get_password(self, s, u): return self.v
    def delete_password(self, s, u): self.v = None

def test_status_masks_never_plaintext():
    b = FakeBackend(); cs = CredentialStore(b); cs.set_key("sk-abcdef1234567890")
    st = cs.status()
    assert st["configured"] is True
    assert "sk-abcdef1234567890" not in str(st) and st["masked"].endswith("7890")

def test_dotenv_disabled_by_default(tmp_path):
    p = tmp_path/".env"; p.write_text("OPENAI_API_KEY=sk-fromdotenv")
    cs = CredentialStore(FakeBackend(), allow_dotenv=False, dotenv_path=str(p))
    assert cs.get_key() is None

def test_env_fallback():
    cs = CredentialStore(FakeBackend(), env={"OPENAI_API_KEY":"sk-env"})
    assert cs.get_key() == "sk-env"

def test_clear():
    b = FakeBackend(); cs = CredentialStore(b); cs.set_key("x"); cs.clear()
    assert cs.status()["configured"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/credentials/test_store.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/credentials/store.py
SERVICE, USER = "aegiscode", "llm_api_key"

class CredentialStore:
    def __init__(self, backend, allow_dotenv=False, env=None, dotenv_path=None):
        self.backend, self.allow_dotenv = backend, allow_dotenv
        self.env, self.dotenv_path = env or {}, dotenv_path
    def set_key(self, value): self.backend.set_password(SERVICE, USER, value)
    def clear(self):
        try: self.backend.delete_password(SERVICE, USER)
        except Exception: pass
    def get_key(self):
        try:
            v = self.backend.get_password(SERVICE, USER)
        except Exception:
            v = None
        if v: return v
        if self.allow_dotenv and self.dotenv_path:
            for line in open(self.dotenv_path):
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=",1)[1].strip()
        return self.env.get("OPENAI_API_KEY")
    def status(self):
        v = self.get_key()
        return {"configured": bool(v),
                "masked": (v[:2] + "…" + v[-4:]) if v else None}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/credentials/test_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/credentials/store.py tests/credentials/test_store.py
git commit -m "feat: credential store keyring/.env/env, fail-safe, masked status"
```

---

### Task 25: Self-written secret scanner ✅ DONE (b39c3ca, +f271fd7)

**Files:**
- Create: `aegiscode/credentials/scanner.py`, `tests/credentials/test_scanner.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `scan_text(text) -> list[Finding]` and `scan_paths(paths) -> list[Finding]` (`Finding(path, line_no, pattern)`); reuses the same key patterns as the redactor. Used by CI + a `aegiscode` self-check.

- [ ] **Step 1: Write the failing test**
```python
# tests/credentials/test_scanner.py
from aegiscode.credentials.scanner import scan_text, scan_paths

def test_detects_planted_key():
    f = scan_text("x = 'sk-abcdef1234567890abcdef1234567890'")
    assert f and f[0].pattern

def test_clean_text_no_findings():
    assert scan_text("no secrets here") == []

def test_scan_file(tmp_path):
    p = tmp_path/"c.py"; p.write_text("KEY=AKIAIOSFODNN7EXAMPLE\n")
    assert scan_paths([str(p)])[0].line_no == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/credentials/test_scanner.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**
```python
# aegiscode/credentials/scanner.py
import re
from dataclasses import dataclass

_PATTERNS = [re.compile(p) for p in [
    r"sk-ant-[A-Za-z0-9\-_]{20,}", r"sk-[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}", r"(?i)(KEY|TOKEN|SECRET|PASSWORD)\s*=\s*[A-Za-z0-9\-_+/=]{16,}"]]

@dataclass
class Finding:
    path: str; line_no: int; pattern: str

def scan_text(text, path="<text>"):
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for p in _PATTERNS:
            if p.search(line): out.append(Finding(path, i, p.pattern))
    return out

def scan_paths(paths):
    out = []
    for p in paths:
        try: out += scan_text(open(p, encoding="utf-8", errors="ignore").read(), p)
        except OSError: continue
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/credentials/test_scanner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/credentials/scanner.py tests/credentials/test_scanner.py
git commit -m "feat: self-written secret scanner (CI + self-check)"
```

---

## Milestone 6 — Service / Interface

### Task 26: ApplicationService (create/query/approve/cancel + persistence)

**Files:**
- Create: `aegiscode/service/__init__.py`, `aegiscode/service/app_service.py`, `aegiscode/persistence/repositories.py`, `tests/service/test_app_service.py`
- Modify: `tests/helpers.py` — **add `make_service(tmp_path, scripted, final_ok, sync=False)`** (wires a MockLLM-backed `HarnessCore` via `harness_factory` + a temp sqlite `ApplicationService`; `sync=True` runs the loop inline for deterministic tests). This extends the `tests/helpers.py` created in Task 23.

**Interfaces:**
- Consumes: `HarnessCore`, `open_db`, `AuditLog`, `AegisConfig`.
- Produces: `class ApplicationService(db, config, harness_factory)` with `create_task(workspace, description) -> task_id` (runs loop in a background thread, or inline when constructed in sync mode, persisting state each turn), `get_task(task_id) -> dict`, `get_events(task_id, since:int) -> list`, `list_approvals(task_id) -> list`, `decide(approval_id, approved) -> None`, `cancel(task_id) -> None`, `get_audit(task_id) -> dict` (events + `verify_chain`, exposes `chain_valid: bool`). Repositories provide row CRUD. Also `make_service` test helper (see Files).

- [ ] **Step 1: Write the failing test** (synchronous mode via injected executor for determinism)
```python
# tests/service/test_app_service.py
from aegiscode.service.app_service import ApplicationService
from tests.helpers import make_service   # wires MockLLM harness + in-memory-ish sqlite

def test_create_and_query(tmp_path):
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "noop task")
    t = svc.get_task(tid)
    assert t["state"] in ("COMPLETED","RUNNING","FAILED")

def test_events_since(tmp_path):
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "noop")
    assert isinstance(svc.get_events(tid, since=0), list)

def test_audit_verify_exposed(tmp_path):
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "noop")
    assert svc.get_audit(tid)["chain_valid"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/service/test_app_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation** — `repositories.py` (insert/select for tasks/steps/approvals) + `app_service.py` orchestrating harness runs, persisting `steps` per turn, exposing `get_audit` calling `AuditLog.verify_chain`. Support `sync=True` (run inline) for tests; background thread otherwise.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/service/test_app_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/service/app_service.py aegiscode/persistence/repositories.py tests/service/test_app_service.py
git commit -m "feat: ApplicationService + repositories (create/query/approve/audit)"
```

---

### Task 27: FastAPI REST (8 endpoints)

**Files:**
- Create: `aegiscode/service/api.py`, `tests/service/test_api.py`
- Modify: `tests/helpers.py` — **add `make_api_client(tmp_path, scripted, final_ok)`** returning a `fastapi.testclient.TestClient` wrapping `build_app(service)` over a `make_service(...)` instance. Reused by Task 28.

**Interfaces:**
- Consumes: `ApplicationService`.
- Produces: FastAPI app with 8 endpoints (SPEC §13 M13): `POST /tasks`, `GET /tasks/{id}`, `GET /tasks/{id}/events?since=N`, `GET /tasks/{id}/approvals`, `POST /approvals/{id}/decision`, `POST /tasks/{id}/cancel`, `GET /tasks/{id}/audit`, `GET /credentials/status`. Tested via `fastapi.testclient.TestClient` with a MockLLM-backed service.

- [ ] **Step 1: Write the failing test**
```python
# tests/service/test_api.py
from fastapi.testclient import TestClient
from tests.helpers import make_api_client   # TestClient over app wired to MockLLM service

def test_create_task_returns_id(tmp_path):
    client = make_api_client(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True)
    r = client.post("/tasks", json={"workspace": str(tmp_path), "description":"noop"})
    assert r.status_code == 200 and "task_id" in r.json()

def test_credentials_status_masked(tmp_path):
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/credentials/status")
    body = r.json()
    assert "masked" in body and "plaintext" not in body

def test_events_endpoint(tmp_path):
    client = make_api_client(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True)
    tid = client.post("/tasks", json={"workspace": str(tmp_path), "description":"n"}).json()["task_id"]
    assert client.get(f"/tasks/{tid}/events?since=0").status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/service/test_api.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation** — FastAPI routers delegating to `ApplicationService`; Pydantic request bodies; `/credentials/status` returns `CredentialStore.status()` only.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/service/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/service/api.py tests/service/test_api.py
git commit -m "feat: FastAPI REST (8 endpoints) over ApplicationService"
```

---

### Task 28: WebUI (static, polling)

**Files:**
- Create: `aegiscode/service/webui/index.html`, `aegiscode/service/webui/app.js`, `aegiscode/service/webui/style.css`; Modify: `aegiscode/service/api.py` (mount static + `GET /`); Test: `tests/service/test_webui_served.py`

**Interfaces:**
- Consumes: the 8 REST endpoints.
- Produces: single-page UI: workspace+task input → start; poll `events?since=N`; render event stream, approval panel (approve/reject), file diffs, final state, audit view + "verify chain" button. Native HTML/CSS/JS only.

- [ ] **Step 1: Write the failing test**
```python
# tests/service/test_webui_served.py
from tests.helpers import make_api_client

def test_root_serves_html(tmp_path):
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/service/test_webui_served.py -v`
Expected: FAIL — `/` not mounted.

- [ ] **Step 3: Write minimal implementation** — static files + mount; `app.js` polls every 1.5s; approval buttons POST decision. (UI logic is browser-side; the automated test only asserts serving. Manual verification steps documented in README.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/service/test_webui_served.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/service/webui aegiscode/service/api.py tests/service/test_webui_served.py
git commit -m "feat: native WebUI (polling event stream + approval panel + audit)"
```

---

### Task 29: CLI (init/run/serve/config/key/demo)

**Files:**
- Create: `aegiscode/cli.py`, `tests/test_cli.py`; Modify: `pyproject.toml` (`[project.scripts] aegiscode = "aegiscode.cli:main"`)

**Interfaces:**
- Consumes: `ApplicationService`, `CredentialStore`, `load_config`.
- Produces: `main(argv)` argparse dispatch: `init` (scaffold aegis.yaml), `run --workspace --task [--watch]`, `serve`, `config` (validate+print), `key set|status|clear` (getpass for set; status masked), `demo` (run mechanism demos).

- [ ] **Step 1: Write the failing test**
```python
# tests/test_cli.py
from aegiscode.cli import main

def test_key_status_not_configured(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("AEGIS_HOME", str(tmp_path))
    main(["key","status"])
    out = capsys.readouterr().out.lower()
    assert "not configured" in out or "configured: false" in out

def test_config_validates(tmp_path, capsys):
    (tmp_path/"aegis.yaml").write_text("limits:\n  max_steps: 25\n")
    rc = main(["config","--path", str(tmp_path/"aegis.yaml")])
    assert rc == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation** — argparse subcommands; `key set` uses `getpass.getpass`; never echo plaintext.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add aegiscode/cli.py pyproject.toml tests/test_cli.py
git commit -m "feat: CLI init/run/serve/config/key/demo"
```

---

## Milestone 7 — Distribution & Demos

### Task 30: Dockerfile + keyring fallback

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `tests/test_docker_build.py` (optional smoke, marked slow)

**Interfaces:**
- Produces: image running `aegiscode serve`; key injected at runtime via `-e`; workspace via `-v ...:/workspace`; keyring-unavailable auto-falls back to env (already handled in T24 `get_key` try/except).

- [ ] **Step 1: Write the failing test** (config-level, not requiring docker daemon)
```python
# tests/test_docker_build.py
import pathlib
def test_dockerfile_has_no_key_and_runtime_cmd():
    df = pathlib.Path("Dockerfile").read_text()
    assert "aegiscode serve" in df
    assert "OPENAI_API_KEY" not in df           # key never baked in
    assert "ENV" not in df or "API_KEY" not in df
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_docker_build.py -v`
Expected: FAIL — Dockerfile missing.

- [ ] **Step 3: Write minimal implementation**
```dockerfile
# Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY aegiscode ./aegiscode
RUN pip install --no-cache-dir -e .
EXPOSE 8000
CMD ["aegiscode", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_docker_build.py -v`
Expected: PASS. Manual: `docker build -t aegiscode . && docker run -p 8000:8000 -e OPENAI_API_KEY=... -v $PWD/demo:/workspace aegiscode`.

- [ ] **Step 5: Commit**
```bash
git add Dockerfile .dockerignore tests/test_docker_build.py
git commit -m "feat: Dockerfile (runtime key injection, /workspace mount)"
```

---

### Task 31: Mechanism demos (§A.6, four demos)

**Files:**
- Create: `demos/demo1_dangerous_denied.py`, `demos/demo2_feedback_loop.py`, `demos/demo3_symlink_escape.py`, `demos/demo4_superseded.py`, `tests/demos/test_demos.py`; Modify: `aegiscode/cli.py` (`demo` runs all four)

**Interfaces:**
- Consumes: HarnessCore + governance units + MockLLM. Each demo is both a runnable script and asserted by `test_demos.py`.
- Produces: four deterministic, network-free demos matching SPEC §16.4 (① rm -rf DENY; ② failure→action change→final-verifier COMPLETED; ③ symlink escape DENY; ④ SUPERSEDED re-approval).

- [ ] **Step 1: Write the failing test**
```python
# tests/demos/test_demos.py
from demos import demo1_dangerous_denied, demo2_feedback_loop, demo3_symlink_escape, demo4_superseded

def test_demo1(): assert demo1_dangerous_denied.run() == {"executed":0,"decision":"DENY"}
def test_demo2(): r = demo2_feedback_loop.run(); assert r["completed"] and r["action_changed"]
def test_demo3(): assert demo3_symlink_escape.run()["decision"] == "DENY"
def test_demo4(): assert demo4_superseded.run()["superseded"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/demos/test_demos.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Write minimal implementation** — each demo wires MockLLM + real components (reuse `tests/helpers`) and returns a small dict asserted above.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/demos/test_demos.py -v && aegiscode demo`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add demos tests/demos aegiscode/cli.py
git commit -m "feat: four MockLLM mechanism demos (dangerous/feedback/symlink/superseded)"
```

---

### Task 32: CI pipeline (unit-test job + secret scan + docker build)

**Files:**
- Create: `.gitlab-ci.yml`

**Interfaces:**
- Produces: pipeline with a job named exactly `unit-test` running `make test`; a `secret-scan` job (self-written scanner + gitleaks); a `docker-build` job (SPEC §clause: container distribution builds image in CI).

- [ ] **Step 1: Write the failing test** (lint the CI file for the required job name)
```python
# tests/test_ci_config.py
import yaml, pathlib
def test_unit_test_job_exists():
    ci = yaml.safe_load(pathlib.Path(".gitlab-ci.yml").read_text())
    assert "unit-test" in ci
    assert "make test" in str(ci["unit-test"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ci_config.py -v`
Expected: FAIL — file missing.

- [ ] **Step 3: Write minimal implementation**
```yaml
# .gitlab-ci.yml
stages: [test, security, build]
unit-test:
  stage: test
  image: python:3.12-slim
  script:
    - pip install -e ".[dev]"
    - make test
secret-scan:
  stage: security
  image: python:3.12-slim
  script:
    - pip install -e .
    - python -c "from aegiscode.credentials.scanner import scan_paths; import sys,glob; f=scan_paths(glob.glob('**/*.py',recursive=True)); sys.exit(1 if f else 0)"
docker-build:
  stage: build
  image: docker:latest
  services: [docker:dind]
  script:
    - docker build -t aegiscode .
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ci_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add .gitlab-ci.yml tests/test_ci_config.py
git commit -m "ci: unit-test job + secret scan + docker build"
```

---

## Task Dependency Summary

| Task | Depends on | Parallel-safe with |
|---|---|---|
| T1 scaffold | — | (blocks all) |
| T2 config | T1 | T3, T4 |
| T3 redactor | T1 | T2, T4 |
| T4 persistence | T1 | T2, T3 |
| T5 LLM base+mock | T1 | T7, T8 |
| T6 adapters | T5 | — |
| T7 action parser | T1 | T5, T8 |
| T8 tool registry | T1 | T5, T7 |
| T9 file tools | T8 | — |
| T10 policy engine | T1, T2 (re-exports config `Decision`) | — |
| T11 path fence | T10 | T12 |
| T12 dispatcher | T10, T11, T8 | — |
| T13 command lexer | T1 | T11 |
| T14 command rules | T13 | — |
| T15 approval SM (defines `fingerprint()`) | T10 | T16, T17 |
| T16 command tool | T14, T8 | T17 |
| T17 run_tests+finish | T8 | T16 |
| T18 feedback | T3, T8 | T19, T20 |
| T19 audit chain | T3, T4 | T18, T20 |
| T20 memory store | T4, T3, T25(scanner) | T18, T19 |
| T21 context builder | T20 | — |
| T22 termination | T1 | — |
| T23 HarnessCore | T5,T7,T8,T9,T12,T14,T15,T16,T17,T18,T19,T21,T22 | — |
| T24 credential store | T1 | T25 |
| T25 secret scanner | T1 | T24 |
| T26 app service | T23, T4 | — |
| T27 REST API | T26 | T29 |
| T28 WebUI | T27 | — |
| T29 CLI | T23, T24 | T27, T28 |
| T30 Dockerfile | T27 | T32 |
| T31 demos | T23 + governance set | — |
| T32 CI | T1 (+make test) | T30 |

**Note:** T20 (memory store) uses T25's `scan_text` for secret-refusal; schedule T25 before T20 (both are otherwise small). The dependency graph in the header lists parallel worktree groups.

---

## Self-Review

**1. Spec coverage** — each SPEC module maps to task(s):
M1 主循环→T22,T23 · M2 LLM→T5,T6 · M3 动作协议→T7 · M4 工具分发→T8,T9,T16,T17 · M5 治理甲→T13,T14,T16 · M6 治理乙→T11,T12 · M7 审批→T15 · M8 审计→T19 · M9 反馈→T18 · M10 记忆→T20,T21 · M11 配置→T2 · M12 凭据→T24,T25 · M13 WebUI/API→T26,T27,T28 · M14 分发→T30 · M15 演示→T31. Governance engine core→T10. CI (§16.3/清单6)→T32. Golden path (§4)→T23 demo②. Four demos (§16.4)→T31. **No uncovered SPEC module.**

**2. Placeholder scan** — every code step contains real code or an explicit named-signature description (T23/T26/T27/T28/T29/T31 steps 3 reference exact functions/endpoints defined in their Interfaces block). No "TBD/TODO/handle edge cases".

**3. Type consistency** — cross-task signatures verified: `ToolResult` fields (T8) used identically in T9/T16/T17/T18; `GovernanceVerdict(decision,rule_id,reason)` (T10) used in T12/T14; `Decision` enum (T10) used in T12/T14/T23; `fingerprint(action)` (T15) used in T23; `classify`/`ProgressTracker` (T18) used in T23; `decide_termination`/`LoopCounters`/`TerminationReason` (T22) used in T23; `AuditLog.append/verify_chain` (T19) used in T23/T26; `MemoryStore` (T20) + `scan_text` (T25) consistent; `CredentialStore.status()` (T24) used in T27/T29.

**Split-governance requirement (your #6):** governance is 6 separate files/tasks — `decision.py`+`engine.py` (T10), `path_fence.py` (T11), `dispatcher.py` (T12), `command_lexer.py` (T13), `command_rules.py` (T14), `approval.py`+`fingerprint` (T15). No monolithic `guardrail.py`.

**TDD (your #5):** every task follows write-failing-test → run-fail → minimal-impl → run-pass → commit.

---

*Plan complete. This document contains no executed code; implementation awaits execution-phase approval.*