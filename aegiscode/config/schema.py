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
    llm_max_retries: int = 3
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
    CommandRule(argv0="git",    args_contain=["push"],            decision=Decision.DENY),
    CommandRule(argv0="git",    args_contain=["reset", "--hard"], decision=Decision.DENY),
    CommandRule(argv0="git",    args_contain=["clean"],           decision=Decision.DENY),
    CommandRule(argv0="git",    args_contain=["commit"],          decision=Decision.REQUIRE_APPROVAL),
    CommandRule(argv0="pip",    args_contain=["install"],         decision=Decision.REQUIRE_APPROVAL),
    CommandRule(argv0="python", args_contain=["-c"],              decision=Decision.DENY),
    CommandRule(argv0="python", args_contain=["-m"],              decision=Decision.DENY),
]


class Governance(_Strict):
    command_allowlist: list[str] = [
        "python", "python3", "pip", "pytest", "ruff", "mypy", "git", "ls", "cat"
    ]
    command_rules: list[CommandRule] = Field(
        default_factory=lambda: list(_DEFAULT_COMMAND_RULES)
    )  # baked-in; YAML fully overrides
    sensitive_file_patterns: list[str] = [".env", ".git/", "*.pem", "*.key", "*credentials*"]
    write_allowlist_dirs: list[str] = ["src/", "tests/"]
    default_decisions: DefaultDecisions = DefaultDecisions()


class Workspace(_Strict):
    root: str = "/workspace"


class Tools(_Strict):
    enabled: list[str] = [
        "list_files", "read_file", "search_text", "write_file",
        "run_tests", "run_command", "finish"
    ]
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
