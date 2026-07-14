"""AegisCode mechanism-demo orchestrator — the `make demo` entry point (§3).

Runs the THREE graded MockLLM-deterministic mechanism demos in order and prints
a human-readable, per-check PASS/FAIL report (§3.3). Exit code is 0 iff every
selected demo's every contract check passes; any failure — a false check OR a
demo that raises — yields a non-zero exit (§3.2.10-12). Nothing here swallows a
failure and returns success.

The three demos map to the three core mechanisms the harness is graded on:
  [Demo 1/3] Dangerous action denial      -> demos.demo1_dangerous_denied
  [Demo 2/3] Feedback-driven repair       -> demos.demo2_feedback_loop
  [Demo 3/3] Approval binding + invalidation -> demos.demo3_approval_binding

Each underlying demo's ``run()`` returns a contract dict of booleans/counters;
this module maps those keys to labeled PASS lines. The demos are fully
self-contained (MockLLM, tmp workspace, zero network) — see their module
docstrings. This orchestrator is intentionally thin: it only sequences, checks,
formats, and computes the exit code, so the mechanism proofs live with the demos.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Callable

from demos import (
    demo1_dangerous_denied,
    demo2_feedback_loop,
    demo3_approval_binding,
)

# A single contract check: a human-readable label + a predicate over the demo's
# result dict. The label is what prints after "PASS:" / "FAIL:".
Check = tuple[str, Callable[[dict], bool]]


@dataclass
class DemoSpec:
    name: str          # stable CLI selector (--only <name>)
    index: int         # 1-based position, drives the "[Demo N/3]" header
    title: str         # human title shown in the header
    run: Callable[[], dict]
    checks: list[Check]


# --- per-demo contract checks (map each demo's result dict to graded PASS lines) ---

_DEMOS: list[DemoSpec] = [
    DemoSpec(
        name="guardrail",
        index=1,
        title="Dangerous action denial",
        run=demo1_dangerous_denied.run,
        checks=[
            ("dangerous command was denied", lambda r: r["decision"] == "DENY"),
            ("tool execution count = 0", lambda r: r["executed"] == 0),
            ("audit event recorded (GOVERNANCE_DECISION=DENY)", lambda r: r["audit_has_deny"]),
            ("denial carries a policy rule_id", lambda r: bool(r["deny_rule_id"])),
            ("agent received POLICY_DENIED feedback", lambda r: r["feedback_is_policy_denied"]),
        ],
    ),
    DemoSpec(
        name="feedback",
        index=2,
        title="Feedback-driven repair",
        run=demo2_feedback_loop.run,
        checks=[
            ("validation failure entered next context",
             lambda r: r["test_failure_seen_in_round3_context"]),
            ("next action changed after the failure", lambda r: r["action_changed"]),
            ("corrected fix landed on disk", lambda r: r["fix_on_disk"]),
            ("final completion gated on objective re-verification",
             lambda r: r["completed"]),
        ],
    ),
    DemoSpec(
        name="approval",
        index=3,
        title="Approval binding and invalidation",
        run=demo3_approval_binding.run,
        checks=[
            ("action paused for approval (0 executions at pause)",
             lambda r: r["paused_for_approval"]),
            ("approval saved the normalized action + fingerprint",
             lambda r: r["approval_saved_normalized"]),
            ("original action executed after approval",
             lambda r: r["original_executed_after_approval"]),
            ("modified action invalidated old approval (SUPERSEDED)",
             lambda r: r["modified_superseded"]),
            ("modified action was NOT executed", lambda r: r["modified_not_executed"]),
            ("audit records the full APPROVED->SUPERSEDED flow",
             lambda r: r["audit_has_approval_flow"]),
        ],
    ),
]

_DEMO_BY_NAME: dict[str, DemoSpec] = {d.name: d for d in _DEMOS}


def _run_one(spec: DemoSpec) -> bool:
    """Run one demo, print its labeled block, return True iff all checks pass.

    A demo that RAISES is a failure (not a crash): we catch it, print a FAIL
    line, and return False so the orchestrator still emits a summary and a
    non-zero exit. This is what keeps a broken mechanism from masquerading as a
    silent pass.
    """
    print(f"[Demo {spec.index}/3] {spec.title}")
    try:
        result = spec.run()
    except Exception as exc:  # noqa: BLE001 - a raising demo is a FAIL, reported not swallowed
        print(f"FAIL: demo raised {type(exc).__name__}: {exc}")
        print()
        return False

    all_ok = True
    for label, predicate in spec.checks:
        try:
            ok = bool(predicate(result))
        except Exception as exc:  # noqa: BLE001 - a missing/garbage key is a FAIL
            ok = False
            label = f"{label} (check errored: {exc})"
        print(f"{'PASS' if ok else 'FAIL'}: {label}")
        all_ok = all_ok and ok
    print()
    return all_ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aegiscode-demos",
        description="Run AegisCode's three deterministic mechanism demos (MockLLM, zero network).",
    )
    parser.add_argument(
        "--only",
        choices=list(_DEMO_BY_NAME),
        help="run only the named demo (default: run all three in order)",
    )
    args = parser.parse_args(argv)

    if args.only:
        specs = [_DEMO_BY_NAME[args.only]]
    else:
        specs = sorted(_DEMOS, key=lambda d: d.index)

    passed = 0
    failed = 0
    for spec in specs:
        if _run_one(spec):
            passed += 1
        else:
            failed += 1

    print(f"AegisCode mechanism demos: {passed} passed, {failed} failed")
    # Exit code is the graded contract: non-zero iff anything failed.
    return 0 if failed == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
