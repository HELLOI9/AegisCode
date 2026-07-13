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
        with open(abspath, "w") as f:
            f.write(content)
        return ToolResult(tool=self.name, status="success",
                          summary=f"wrote {path}", artifacts={"changed_files": [path]})


class ReadFileTool:
    name = "read_file"

    def run(self, arguments, ctx):
        try:
            with open(ctx.resolve(arguments["path"]), "rb") as fh:
                raw = fh.read()
        except OSError as e:
            return ToolResult(tool=self.name, status="error", category="TOOL_ERROR",
                              summary=f"cannot read {arguments['path']}: {e}")
        if _is_binary(raw):
            return ToolResult(tool=self.name, status="success", summary="binary skipped")
        text = raw.decode(errors="replace")
        return ToolResult(tool=self.name, status="success",
                          summary=f"read {len(text.splitlines())} lines", detail_for_llm=text)


class ListFilesTool:
    name = "list_files"

    def run(self, arguments, ctx):
        root = ctx.resolve(arguments.get("path", "."))
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
                try:
                    with open(fp, "rb") as fh:
                        data = fh.read()
                except OSError:
                    continue
                if _is_binary(data):
                    continue
                for i, line in enumerate(data.decode(errors="replace").splitlines(), 1):
                    if q in line:
                        hits.append(f"{os.path.relpath(fp, base)}:{i}: {line.strip()}")
        return ToolResult(tool=self.name, status="success",
                          summary=f"{len(hits)} matches", detail_for_llm="\n".join(hits))
