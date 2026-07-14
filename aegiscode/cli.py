"""aegiscode/cli.py — command-line interface.

Subcommands: init, run, serve, config, key, demo.

main(argv) takes an explicit argv list (never reads sys.argv directly) so it is
trivially testable. Network-touching paths (run with a real provider, serve
binding a socket) are kept out of the automated tests.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from aegiscode.config.loader import ConfigError, load_config
from aegiscode.config.schema import AegisConfig

_DEFAULT_CONFIG_NAME = "aegis.yaml"

# Commented, valid scaffold that round-trips through load_config. Only a few
# knobs are shown; every field has a schema default so omissions are fine.
_INIT_TEMPLATE = """\
# AegisCode configuration. All keys are optional — omitted values use secure
# defaults baked into the code (governance rules, allowlists, limits).

llm:
  provider: openai      # openai | anthropic | mock
  model: gpt-4o

limits:
  max_steps: 25
  command_timeout_sec: 30

workspace:
  root: /workspace

feedback:
  test_command: pytest -q
"""

# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def _data_dir() -> Path:
    """Directory for the sqlite db. AEGIS_HOME when set, else ~/.aegiscode."""
    home = os.environ.get("AEGIS_HOME")
    base = Path(home) if home else Path.home() / ".aegiscode"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _load_config(path: str | None) -> AegisConfig:
    """Load config from an explicit path, else ./aegis.yaml, else defaults."""
    if path:
        return load_config(path)
    default = Path.cwd() / _DEFAULT_CONFIG_NAME
    if default.exists():
        return load_config(str(default))
    return AegisConfig()


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------


def _cmd_init(args) -> int:
    target = Path(args.path) if args.path else Path.cwd() / _DEFAULT_CONFIG_NAME
    if target.exists() and not args.force:
        print(f"refusing to overwrite existing {target} (use --force)",
              file=sys.stderr)
        return 1
    target.write_text(_INIT_TEMPLATE, encoding="utf-8")
    # Validate the scaffold round-trips before declaring success.
    load_config(str(target))
    print(f"wrote {target}")
    return 0


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------


def _cmd_config(args) -> int:
    try:
        cfg = load_config(args.path)
    except (ConfigError, OSError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    print("config OK")
    print(f"  provider: {cfg.llm.provider}")
    print(f"  model: {cfg.llm.model}")
    print(f"  max_steps: {cfg.limits.max_steps}")
    print(f"  workspace.root: {cfg.workspace.root}")
    print(f"  tools.enabled: {', '.join(cfg.tools.enabled)}")
    return 0


# --------------------------------------------------------------------------
# key set / status / clear
# --------------------------------------------------------------------------


def _cmd_key(args) -> int:
    from aegiscode.credentials.backend import build_credential_store

    store = build_credential_store()

    if args.key_action == "set":
        # getpass never echoes; we NEVER print the plaintext value anywhere.
        value = getpass.getpass("LLM API key: ")
        if not value:
            print("no key entered; nothing stored", file=sys.stderr)
            return 1
        store.set_key(value)
        print("API key stored")
        return 0

    if args.key_action == "status":
        st = store.status()
        if st["configured"]:
            print(f"configured: true  (masked: {st['masked']})")
        else:
            print("configured: false  (not configured)")
        return 0

    if args.key_action == "clear":
        store.clear()
        print("API key cleared")
        return 0

    print(f"unknown key action: {args.key_action}", file=sys.stderr)
    return 2


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------


def _cmd_run(args) -> int:
    from aegiscode.credentials.backend import build_credential_store
    from aegiscode.service.assembly import NoKeyError, build_service

    try:
        cfg = _load_config(args.config)
    except (ConfigError, OSError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    store = build_credential_store()
    db_path = str(_data_dir() / "aegis.db")

    # Run synchronously so the task reaches a terminal state before we return.
    try:
        service = build_service(cfg, store, db_path, sync=True)
    except NoKeyError as exc:
        print(f"cannot run: {exc}", file=sys.stderr)
        return 1

    task_id = service.create_task(workspace=args.workspace, description=args.task)
    print(f"task {task_id}")

    if args.watch:
        _watch(service, task_id)
    return 0


def _watch(service, task_id: str) -> None:
    """Print audit events for the task (already terminal in sync mode)."""
    events = service.get_events(task_id, since=0)
    for ev in events:
        et = ev.get("event_type", "")
        si = ev.get("step_index", "")
        print(f"  [step {si}] {et}")
    row = service.get_task(task_id)
    print(f"state: {row.get('state')}")


# --------------------------------------------------------------------------
# serve
# --------------------------------------------------------------------------


def _cmd_serve(args) -> int:
    import uvicorn

    from aegiscode.credentials.backend import build_credential_store
    from aegiscode.service.api import build_app
    from aegiscode.service.assembly import NoKeyError, build_service

    try:
        cfg = _load_config(args.config)
    except (ConfigError, OSError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    store = build_credential_store()
    db_path = str(_data_dir() / "aegis.db")

    try:
        service = build_service(cfg, store, db_path, sync=False)
    except NoKeyError as exc:
        print(f"cannot serve: {exc}", file=sys.stderr)
        return 1

    app = build_app(service, credential_store=store)

    print("=" * 60)
    print("AegisCode local panel — SECURITY NOTICE")
    print("This API has NO authentication and is for LOCALHOST ONLY.")
    print("Do NOT expose it on a public or shared network interface.")
    print(f"Serving on http://{args.host}:{args.port}  (localhost only)")
    print("=" * 60)

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


# --------------------------------------------------------------------------
# demo — self-contained, zero-network mechanism demos (SPEC §16.4 / §A.6)
# --------------------------------------------------------------------------


def _cmd_demo(args) -> int:
    """Run all four SPEC §16.4 mechanism demos and report PASS/FAIL per demo.

    Each demo lives in the top-level ``demos`` package, is fully self-contained
    (no test-helper imports), zero-network (MockLLM only), and exercises a REAL
    governance / harness / approval mechanism:

      demo①  governance DENIES ``rm -rf /`` (tool never executes)
      demo②  failure feedback drives an action change → verified COMPLETED
      demo③  path fence DENIES a symlink escape to /etc/passwd
      demo④  a changed action after approval is SUPERSEDED

    Returns 0 iff all four satisfy their run() contract; 1 otherwise.
    """
    import aegiscode

    # The demos package sits at the repo root (next to the aegiscode package),
    # both in a source checkout and inside the container (COPY demos ./demos).
    # Ensure that root is importable regardless of the current working dir.
    repo_root = Path(aegiscode.__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from demos import (
            demo1_dangerous_denied,
            demo2_feedback_loop,
            demo3_symlink_escape,
            demo4_superseded,
        )
    except ModuleNotFoundError as exc:  # pragma: no cover - packaging guard
        print(f"cannot load demos package: {exc}", file=sys.stderr)
        return 1

    # (label, module, contract predicate on the returned dict)
    demos = [
        ("demo①", demo1_dangerous_denied,
         lambda r: r == {"executed": 0, "decision": "DENY"}),
        ("demo②", demo2_feedback_loop,
         lambda r: r.get("completed") and r.get("action_changed")),
        ("demo③", demo3_symlink_escape,
         lambda r: r.get("decision") == "DENY"),
        ("demo④", demo4_superseded,
         lambda r: r.get("superseded") is True),
    ]

    all_ok = True
    for label, module, contract in demos:
        try:
            result = module.run()
            passed = bool(contract(result))
        except Exception as exc:  # noqa: BLE001 - a crashing demo is a FAIL
            all_ok = False
            print(f"{label}: FAIL ({type(exc).__name__}: {exc})", file=sys.stderr)
            continue
        all_ok = all_ok and passed
        status = "PASS" if passed else "FAIL"
        stream = sys.stdout if passed else sys.stderr
        print(f"{label}: {status} {result}", file=stream)

    return 0 if all_ok else 1


# --------------------------------------------------------------------------
# argparse wiring + main
# --------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aegiscode", description="AegisCode CLI")
    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="scaffold a default aegis.yaml")
    p_init.add_argument("--path", default=None, help="target file (default ./aegis.yaml)")
    p_init.add_argument("--force", action="store_true", help="overwrite if it exists")
    p_init.set_defaults(func=_cmd_init)

    p_run = sub.add_parser("run", help="create and run a task")
    p_run.add_argument("--workspace", required=True, help="workspace directory")
    p_run.add_argument("--task", required=True, help="task description")
    p_run.add_argument("--watch", action="store_true", help="print events after run")
    p_run.add_argument("--config", default=None, help="config path (default ./aegis.yaml)")
    p_run.set_defaults(func=_cmd_run)

    p_serve = sub.add_parser("serve", help="run the localhost-only FastAPI panel")
    p_serve.add_argument("--host", default="127.0.0.1", help="bind host (localhost)")
    p_serve.add_argument("--port", type=int, default=8000, help="bind port")
    p_serve.add_argument("--config", default=None, help="config path (default ./aegis.yaml)")
    p_serve.set_defaults(func=_cmd_serve)

    p_config = sub.add_parser("config", help="validate + summarise config")
    p_config.add_argument("--path", default=_DEFAULT_CONFIG_NAME, help="config path")
    p_config.set_defaults(func=_cmd_config)

    p_key = sub.add_parser("key", help="manage the LLM API key credential")
    p_key.add_argument("key_action", choices=["set", "status", "clear"])
    p_key.set_defaults(func=_cmd_key)

    p_demo = sub.add_parser("demo", help="zero-network governance interception demo")
    p_demo.set_defaults(func=_cmd_demo)

    return p


def main(argv) -> int:
    """Parse *argv* (a list, not sys.argv) and dispatch. Returns an exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
