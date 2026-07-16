"""RED-first tests proving the three CLI mechanism demos source their MockLLM
scripts from the shared scenario registry (aegiscode/demo/scenarios.py) rather
than from re-hardcoded literals.

Each test imports the real demo module and asserts the exact list it feeds
``MockLLM`` equals ``list(get_scenario(<id>).mock_script)``, read from the
registry on both sides so the test cannot pass by re-pasting expected
literals. A final test confirms `demos.run_demos.main([])` still returns 0
after the refactor (contract dict keys/values unchanged).
"""
from __future__ import annotations

from aegiscode.demo.scenarios import get_scenario


class TestDemo1UsesRegistryScript:
    def test_demo1_uses_registry_script(self):
        from demos import demo1_dangerous_denied as demo1

        expected = list(get_scenario("dangerous-action-denial").mock_script)
        assert demo1._SCRIPT == expected


class TestDemo2UsesRegistryScript:
    def test_demo2_uses_registry_script(self):
        from demos import demo2_feedback_loop as demo2

        expected = list(get_scenario("feedback-driven-repair").mock_script)
        assert demo2._SCRIPT == expected


class TestDemo3UsesRegistryScript:
    def test_demo3_uses_registry_script(self):
        from demos import demo3_approval_binding as demo3

        expected = list(get_scenario("approval-binding-invalidation").mock_script)
        assert demo3._SCRIPT == expected


class TestRunDemosStillPasses:
    def test_run_demos_still_three_pass(self):
        from demos.run_demos import main

        assert main([]) == 0
