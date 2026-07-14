"""SPEC §16.4 demo③ — approval binding + invalidation lifecycle (live harness).

This test asserts the full run() contract of demos/demo3_approval_binding.py.
Every key must be True: the demo drives the REAL HarnessCore through
REQUIRE_APPROVAL → approve+execute the original → a mutated action reusing the
old approval is SUPERSEDED and never runs. The demo itself contains loud
asserts; this test pins the public contract so a broken mechanism fails CI.
"""
from demos.demo3_approval_binding import run


def test_demo3_approval_binding():
    r = run()
    # An approval was required before ANY tool executed (paused with exec count 0).
    assert r["paused_for_approval"] is True
    # The approval request captured the normalized action + its fingerprint.
    assert r["approval_saved_normalized"] is True
    # After approval, the ORIGINAL (unchanged) action executed exactly once.
    assert r["original_executed_after_approval"] is True
    # A changed action reusing the old approval was SUPERSEDED.
    assert r["modified_superseded"] is True
    # ...and therefore did NOT execute (fails closed).
    assert r["modified_not_executed"] is True
    # The audit log (read back through the repository) records the full flow:
    # APPROVAL_DECIDED APPROVED + APPROVAL_DECIDED SUPERSEDED.
    assert r["audit_has_approval_flow"] is True
