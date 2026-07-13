# AGENT_LOG.md — AegisCode 实现过程日志

按时间顺序记录实现阶段关键节点。每条含:时间戳/task、触发的 Superpowers 技能、关键 prompt/context 配置、subagent 输出关键片段或 commit hash、人工干预、教训。

---

## 2026-07-14 · Milestone 0 启动

**技能链**:using-git-worktrees → subagent-driven-development(每 task 一个新 subagent + TDD + 两阶段评审)。
**Worktree**:`.claude/worktrees/m0-foundations`,分支 `worktree-m0-foundations`(→ 一个 PR)。BASE = 38dda6f。

### Task 1 · 项目脚手架 — ✅ 完成 (c6f8f28)
- **技能**:subagent-driven-development;实现 subagent 用 haiku(计划含完整代码,属转写+TDD);评审 subagent 用 sonnet。
- **TDD**:RED = `pytest tests/test_smoke.py` → `ModuleNotFoundError: No module named 'aegiscode'`;GREEN = `make test` → 1 passed。环境用 `uv venv --python 3.12`(uv 无 pip,改 `uv pip install`)。
- **产物**:pyproject.toml / aegiscode/__init__.py / Makefile / tests/__init__.py / tests/test_smoke.py。
- **两阶段评审**:spec ✅、quality Approved;仅 1 条 Minor(pyproject TOML 段间空行,继承自计划,无需改)。
- **人工干预**:haiku 实现 subagent 两次返回被截断的最终消息、且未落 commit / 未写 report。人工介入:①续跑同一 subagent 完成 commit(c6f8f28);②控制器据已验证的 worktree 状态代写 task-1-report.md(已注明)。代码与提交本身正确,无返工。
- **教训**:haiku 在"实现+提交+写报告+回报"这类需要严格收尾的多步任务上易在最后一步掉线;后续 task 若仍用 haiku,需在 dispatch 里强化"提交与报告是完成的必要条件",或改用 sonnet。

### Task 2 · 配置 schema + YAML loader — ✅ 完成 (387c632, fix 4cf0126)
- **技能**:subagent-driven-development;实现与修复 subagent 用 sonnet(比 Task1 复杂:extra=forbid、Decision 枚举、7 条内置规则、env 覆盖、~10 测试);评审 subagent 用 sonnet。
- **TDD**:RED = `pytest tests/config/test_loader.py` → ModuleNotFoundError: aegiscode.config;GREEN = 10 passed,`make test` 11 passed。
- **产物**:aegiscode/config/{__init__,schema,loader}.py + tests/config/test_loader.py + aegis.yaml。含硬化点:`_Strict(extra="forbid")` 基类、Decision 单一真源(config/schema.py)、CommandRule 扁平+argv0 标量、_DEFAULT_COMMAND_RULES 7 条烤进代码默认(secure-by-default)、command_allowlist 含 pip、load_config(env=None) 读 os.environ。
- **两阶段评审**:spec ✅、quality Approved。findings:1 Important(loader.py open() 未关闭句柄→改 with 块)+ 1 Minor(缺"代码默认下 pip install→REQUIRE_APPROVAL"显式测试,直接守 cold-start 的 D-CS15 fail-open)。两者在 4cf0126 修复(11 passed)。Minor(aegis.yaml command_rules 全量替换的 footgun)为文档性,已在样例注释说明,记录不阻塞。
- **人工干预**:无代码代写;修复 subagent 一次到位。控制器对 8 行机械修复直接验证(with 块 + 新测试就位、11 passed)代替再派评审 subagent(与 skill"评审模型按 diff 规模缩放"一致)。
- **教训**:sonnet 单趟即完成实现+提交+报告,收尾可靠,优于 haiku。
