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

### Task 3 · 脱敏器 redactor — ✅ 完成 (aa8111d, +f214e4c)
- **技能**:subagent-driven-development;实现/评审均 sonnet。
- **TDD**:RED = 模块不存在 ModuleNotFoundError;GREEN = 5 新测试通过,`make test` 16→18 passed。
- **产物**:aegiscode/security/{__init__,redactor.py} + tests/security/test_redactor.py。`redact(text, workspace_root=None)`:sk-ant-/sk-/AKIA/KEY=TOKEN=PASSWORD=SECRET= 四族正则(sk-ant- 先于 sk- 保证顺序)+ workspace 绝对路径→相对(rstrip 尾斜杠、先长后短替换)。纯 stdlib、确定性。
- **两阶段评审**:spec ✅、quality Approved。2 Minor:①AWS `AKIA[0-9A-Z]{16}` 用精确 16(真实 key 恒 20 字符,正确,不改);②通用 KEY=/TOKEN= 族无独立测试(anthropic 测试里 sk-ant- 先命中、该族零直接覆盖)。②在 f214e4c 补 2 个隔离测试修复(18 passed)。
- **人工干预**:无代码代写;补测试 subagent 一次到位。
- **教训**:评审发现"某正则族被前序族遮蔽、零直接覆盖"的测试盲区——对安全关键、被多模块复用的工具,隔离测试值得补。

### Task 4 · SQLite 持久层 — ✅ 完成 (158a744)
- **技能**:subagent-driven-development;实现/评审均 sonnet。
- **TDD**:RED = 模块不存在;GREEN = 2 新测试(6 表齐全 + journal_mode=wal),`make test` 20 passed。
- **产物**:aegiscode/persistence/{__init__,db.py,schema.sql} + tests/persistence/test_db.py。`open_db(path)`:isolation_level=None(autocommit,WAL 需在事务外)+ PRAGMA journal_mode=WAL + foreign_keys=ON + executescript(schema.sql,经 `Path(__file__).with_name` 定位)。6 表(tasks/steps/approval_requests/audit_events/memories/task_snapshots)含 SPEC §9 关键字段(hash 链 prev_hash/hash、memories.confirmed/source、approval.action_fingerprint 等),全部 IF NOT EXISTS(幂等)。
- **两阶段评审**:spec ✅、quality Approved。3 Minor 全不阻塞:import 单行风格(继承计划)、foreign_keys=ON 但 schema 未声明 FK REFERENCES(计划 DDL 本就未含,记入最终评审考量)、测试风格。均未修(不擅自偏离计划 DDL)。
- **人工干预**:无。
- **里程碑**:Milestone 0(基础)4 个 task 全部完成。

### 全分支最终评审(Milestone 0)— READY TO MERGE
- **评审 subagent**:opus(最强模型,按 skill 要求最终评审用最强档)。范围:merge-base 38dda6f..548a33b,10 commits。
- **结论**:READY TO MERGE,无 Critical/Important。
- **新发现 M-1(Minor,真实潜伏 bug)**:redactor 末行 `replace(workspace_root,"")` 未锚定路径边界,`/workspace-backup/...` 会被误删成 `-backup/...`。M0 中脱敏器尚未接线故休眠,且属"过度脱敏"非泄漏;但它是安全关键、被 4 个后续模块复用的工具,故当场修复(7d980ae):改用 `re.sub` 锚定到 `/`|行尾|`:` 边界,加 2 个回归测试(sibling 不被动、bare root 被删),老测试 test_rewrites_workspace_absolute_paths 仍过,22 passed。
- **延后项(不阻塞合并)**:M-2 fastapi/uvicorn 作硬依赖(M13 落地时拆到 optional group);carried-3(aegis.yaml command_rules 全量替换=文档、FK pragma 无 FK=计划 DDL 如此、import/TOML 风格=装饰性)。
- **人工干预**:M-1 修复由控制器决定"当场修而非延后"(安全关键工具 + 一行修 + 被多模块复用),派 sonnet 修复 subagent 一次到位。
- **下一步**:finishing-a-development-branch(建 PR)。测试基线:22 passed,输出 pristine。

---

## 2026-07-14 · Milestone 1 启动(新 worktree)
**Worktree**:`.claude/worktrees/m1-decision-tools`,分支 `worktree-m1-decision-tools`(base = main @ fac0127,M0 经 PR#1 merge 已并入)。基线 `make test` = 22 passed。
**模块**:T5 LLM base+Mock、T6 适配器、T7 动作协议、T8 工具注册、T9 文件工具。依赖仅 T1/T2(已在 main)。实现/评审 sonnet,最终评审 opus。

### Task 5 · LLMClient 接口 + MockLLM — ✅ 完成 (597a8ac, fix 014cb16)
- **TDD**:RED = 模块不存在;GREEN = 3 新测试,`make test` 25 passed。
- **产物**:aegiscode/llm/{__init__,base.py,mock.py}。`LLMClient(ABC).complete(messages)->str`;`MockLLM(scripted_responses)` 按序返回 + `received_messages` 记录每轮 messages + `MockExhaustedError`。零网络零 key——离线确定性测试基座(§A.4C/§16.2)。
- **两阶段评审**:spec ✅、quality Approved。1 Minor:received_messages 存 caller 列表引用(aliasing),caller 跨轮改 messages 会污染记录。因 MockLLM 是后续"失败反馈进入下一轮"断言(demo②)基础工具,当场修(014cb16):存 `list(messages)` 浅拷贝 + 回归测试。26 passed。
- **人工干预**:控制器决定修此 Minor(基座工具、一行修、防后续断言被静默污染)。

### Task 6 · OpenAI + Anthropic 适配器 — ✅ 完成 (a7355d8, fix 034f39e)
- **TDD**:RED = 模块不存在;GREEN = 2 新测试(注入 fake http_post,零网络),`make test` 28 passed。
- **产物**:aegiscode/llm/{openai_adapter,anthropic_adapter}.py。均 LLMClient 子类,可注入 http_post(默认 _real_post 用 urllib)。OpenAIAdapter 取 choices[0].message.content、base_url 可配;AnthropicAdapter 把 system 角色抽出到顶层 system 字段、body 仅留非 system 消息、取 content[].text。测试断言 system 拆分契约,不触网。
- **两阶段评审**:spec ✅、quality Approved。4 Minor:①函数内延迟 import(风格)②无 system 时 system="" (Anthropic 接受)③测试里 fake_anthropic_post 死代码 ④base_url 无测试覆盖。③④在 034f39e 修(删死代码 + 加 test_openai_uses_custom_base_url),29 passed;①②延后(继承计划/无害)。
- **人工干预**:控制器决定修 ③④(死代码清理 + spec 必需特性零覆盖),①②延后。
