"""Provider-agnostic prompt construction (SPEC Appendix B).

The Harness Core owns the single PromptBuilder; adapters never build prompts.
system_prompt + tool_protocol are rendered from config + the live ToolRegistry,
so disabled tools are structurally absent and governance values are concrete.
"""
from __future__ import annotations


class PromptBuilder:
    def __init__(self, config, registry):
        self.config = config
        self.registry = registry

    def system_prompt(self, remaining_steps: int) -> str:
        g = self.config.governance
        sensitive = ", ".join(g.sensitive_file_patterns)
        allowlist = ", ".join(g.command_allowlist)
        rules = "; ".join(
            f"{r.argv0} {' '.join(r.args_contain)} -> {r.decision.value}"
            for r in g.command_rules
        )
        return (
            "You are AegisCode, a coding agent running INSIDE the AegisCode "
            "harness. You have NO direct access to the file system or the shell. "
            "Every effect happens ONLY through a tool call, which is "
            "parameter-validated, governed, executed, and audited by the harness.\n"
            "\n"
            "Rules you must follow:\n"
            "- Return EXACTLY ONE structured action per turn (see the tool "
            "protocol). Never describe multiple actions.\n"
            "- Use only the tools listed in the tool protocol; no other tool "
            "exists for you.\n"
            "- Operate only within the current workspace. Do NOT use path "
            "traversal ('..'), absolute paths, or touch sensitive files "
            f"({sensitive}).\n"
            f"- Command allowlist: {allowlist}. Governed command rules: {rules}.\n"
            "- After any tool failure, governance denial, parse error, or pytest "
            "failure, read the feedback and change your next action accordingly.\n"
            "- Never claim you performed an action you did not actually emit as a "
            "tool call.\n"
            "- Emit the `finish` action ONLY after the tests objectively pass "
            "(pytest exit code 0); the harness independently re-runs pytest before "
            "accepting completion.\n"
            f"- You have {remaining_steps} step(s) remaining."
        )

    def tool_protocol(self) -> str:
        return (
            "TOOL PROTOCOL — respond with a SINGLE JSON object in a ```json "
            "fenced block, and nothing else that could be mistaken for JSON:\n"
            "```json\n"
            '{"thought": "<your reasoning>", "tool": "<tool name>", '
            '"arguments": {<tool arguments>}, "expectation": "<what you expect>"}\n'
            "```\n"
            "`thought` and `expectation` are optional; `tool` and `arguments` are "
            "required. `arguments` must match the selected tool's schema below.\n"
            "\n"
            "Available tools:\n"
            + self.registry.describe()
        )
