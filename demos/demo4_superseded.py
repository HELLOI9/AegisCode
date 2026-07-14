"""SPEC §16.4 demo④ — SUPERSEDED re-approval guard.

Mechanism: an approval is bound to a *fingerprint* of the exact action the
human saw. When the agent resumes after approval, ``validate_resume`` re-checks
the current action's fingerprint against the approved one. If the agent tries to
slip in a DIFFERENT action (changed arguments), the fingerprints diverge and a
``SupersededError`` is raised — the stale approval cannot authorize new work.

This proves approval governance depth: approving action A does not grant a blank
cheque for action B. The identical action A still validates cleanly.
"""
from __future__ import annotations

from aegiscode.governance.approval import (
    SupersededError,
    fingerprint,
    validate_resume,
)
from aegiscode.protocol.action import Action


def run() -> dict:
    """Approve action A, then resume with a changed action B.

    Returns ``{"superseded": <bool>, "identical_ok": <bool>}``.
    Contract: ``superseded is True`` — the changed action B correctly raised
    ``SupersededError``. ``identical_ok is True`` — the unchanged action A
    validated without error.
    """
    # Action A: the exact action the human approved.
    action_a = Action(
        tool="run_command",
        arguments={"command": "git commit -m 'apply reviewed patch'"},
    )
    approved_fp = fingerprint(action_a)

    # Action B: a DIFFERENT action (changed arguments) the agent tries to resume
    # with. It must NOT ride on A's approval.
    action_b = Action(
        tool="run_command",
        arguments={"command": "git push --force origin main"},
    )

    superseded = False
    try:
        validate_resume(approved_fp, action_b)
    except SupersededError:
        superseded = True

    # The identical, still-approved action must validate cleanly (no raise).
    identical_ok = True
    try:
        validate_resume(approved_fp, action_a)
    except SupersededError:
        identical_ok = False

    assert superseded, "changed action was NOT superseded — approval guard broken"
    assert identical_ok, "identical action was wrongly superseded"

    return {"superseded": superseded, "identical_ok": identical_ok}


if __name__ == "__main__":  # pragma: no cover
    r = run()
    print(
        "demo④ superseded re-approval: "
        f"superseded={r['superseded']} identical_ok={r['identical_ok']} "
        "(changed action rejected, identical action still valid)"
    )
