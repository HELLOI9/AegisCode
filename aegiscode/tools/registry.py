class ToolRegistry:
    def __init__(self): self._tools = {}
    def register(self, tool): self._tools[tool.name] = tool
    def get(self, name): return self._tools.get(name)
    def names(self): return list(self._tools)

    def describe(self) -> str:
        """Render a deterministic spec block for every REGISTERED tool.

        Disabled tools are never registered (assembly builds the registry from
        config.tools.enabled), so they cannot appear here. Iteration order is
        registration order (dict preserves insertion), so output is stable.
        """
        blocks = []
        for name in self._tools:
            t = self._tools[name]
            lines = [f"- {t.name}: {t.description}"]
            params = getattr(t, "parameters", {})
            if not params:
                lines.append("    (no arguments)")
            for pname, meta in params.items():
                req = "required" if meta.get("required") else "optional"
                note = meta.get("note", "")
                lines.append(f"    - {pname} ({meta.get('type','string')}, {req}): {note}")
            blocks.append("\n".join(lines))
        return "\n".join(blocks)
