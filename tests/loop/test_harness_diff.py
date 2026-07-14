# tests/loop/test_harness_diff.py
"""TDD (T28 review fix): the TOOL_EXECUTED audit payload must surface the
changed_files list produced by write tools, so the WebUI diff panel (SPEC §13,
mandatory) has data to render. Full textual snapshot diffs stay deferred to v2
(SPEC line 113).
"""

from tests.helpers import make_harness
from aegiscode.loop.termination import TerminationReason


def _tool_executed_events(spy):
    return [e for e in spy.audit_events if e["event_type"] == "TOOL_EXECUTED"]


def test_tool_executed_payload_carries_changed_files_for_write(tmp_path):
    # A write action populates result.artifacts["changed_files"]; the harness
    # must forward that into the TOOL_EXECUTED audit payload.
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"write_file","arguments":{"path":"src/m.py","content":"x = 1\\n"}}',
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True)
    reason = h.run("write a file")
    assert reason == TerminationReason.COMPLETED

    write_events = [e for e in _tool_executed_events(spy) if e["tool"] == "write_file"]
    assert write_events, "expected a TOOL_EXECUTED event for write_file"
    ev = write_events[0]
    # Existing keys unchanged.
    assert ev["tool"] == "write_file"
    assert ev["status"] == "success"
    # The v1 "diff" data: which files the tool touched.
    assert "changed_files" in ev, "TOOL_EXECUTED payload must include changed_files"
    assert ev["changed_files"] == ["src/m.py"]


def test_tool_executed_payload_omits_changed_files_when_no_file_touched(tmp_path):
    # run_tests / finish do not touch files, so the payload must NOT gain a
    # noisy empty changed_files key (backward-compatible, additive-only).
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"run_tests","arguments":{}}',
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True)
    h.run("run tests then finish")

    for ev in _tool_executed_events(spy):
        if ev["tool"] != "write_file":
            assert "changed_files" not in ev, (
                f"{ev['tool']} touched no files; payload must not add changed_files"
            )
