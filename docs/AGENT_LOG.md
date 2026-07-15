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

### Task 7 · Action 模型 + 稳健解析器 — ✅ 完成 (3362c6d, fix f33e0c2)
- **TDD**:RED = 模块不存在;GREEN = 4 新测试,`make test` 33 passed。
- **产物**:aegiscode/protocol/{__init__,action.py,parser.py}。Action={thought,tool,arguments,expectation?}(无 is_final)。parse_action:优先 ```json 围栏,否则取最后一个合法顶层 JSON 对象,再 Pydantic 校验;失败抛 ActionParseError。
- **两阶段评审**:**Needs fixes**——1 Important(真实 bug):初版 `_last_balanced` 是字符级括号计数,对"JSON 字符串值内含 `{`/`}`"(如 write_file 的 content 是代码)会误配、截断→对合法输入误报 ActionParseError。违反 SPEC §M3"稳健 JSON 提取"。判定为"计划示例代码的弱点,非规约选择",当场修。
- **修复 f33e0c2**:改用 `json.JSONDecoder().raw_decode()` 逐 `{` 位置扫描(尊重 JSON 字符串转义),取最后一个成功解析的 dict;保持 parse_action/ActionParseError 公共名不变;补 2 个 braces-in-string 回归测试 + 异常链 from e。6 parser 测试全过(4 原 + 2 新),`make test` 35 passed。控制器直接验证(raw_decode 就位 + 6 测试过)代替再派评审。
- **教训**:计划里"手写括号计数器"这类看似完整的示例代码可能不满足 spec 的"稳健"要求;评审用一个具体风险(字符串内括号)探到了它。这类"示例代码弱点"应按 spec 意图修复,而非因"计划这么写"就放行。

### Task 8 · ToolResult + 工具注册表/接口 — ✅ 完成 (ccbd1de)
- **TDD**:RED = 模块不存在;GREEN = 3 新测试,`make test` 38 passed。
- **产物**:aegiscode/tools/{__init__,result.py,base.py,registry.py}。ToolResult(BaseModel,9 字段+默认);Tool(Protocol) name+run;ToolRegistry register/get(未知→None)/names。仅基座,无具体工具(符合 YAGNI)。
- **两阶段评审**:spec ✅、quality Approved。2 Minor:ToolRegistry.get/register/names 缺类型注解(cosmetic,继承计划,mypy 可受益)。按 skill 将 Minor 记入账本交最终评审 triage,不即时修。
- **人工干预**:无。

### Task 9 · 文件工具(list/read/search/write)— ✅ 完成 (b65fed1, fix 4e9a98f)
- **TDD**:RED = 模块不存在;GREEN = 4 新测试,`make test` 42 passed。
- **产物**:aegiscode/tools/file_tools.py。四工具纯 IO(路径经 ctx.resolve,治理留给后续 dispatcher):WriteFileTool 写前查 write_max_bytes(用 encode 字节长)+ctx.snapshot+changed_files artifact;ReadFileTool NUL 嗅探→binary skipped;SearchTextTool os.walk+跳二进制;ListFilesTool 排序 listdir。
- **两阶段评审**:spec ✅、quality Approved。1 Important(2 处 open().read() 泄漏句柄,与 T2 同类 bug;WriteFileTool 已用 with)+2 Minor(ListFilesTool 零测试覆盖、ReadFileTool 坏路径抛裸异常违反 ToolResult 契约)。全部在 4e9a98f 修:两读改 with、ReadFileTool 坏路径返回 TOOL_ERROR 结构化结果、补 ListFilesTool+坏路径测试。44 passed。
- **人工干预**:控制器决定合并修 Important+2 Minor(句柄泄漏是重复 bug 类;坏路径必须走 ToolResult 契约否则主循环会崩而非收到 TOOL_ERROR 反馈)。
- **里程碑**:Milestone 1(决策与工具基座)5 个 task 全部完成。下一步:全分支最终评审(opus)→ PR。

### 全分支最终评审(Milestone 1)— READY TO MERGE
- **评审 subagent**:opus。范围 fac0127..2515d1e,14 commits。
- **结论**:READY TO MERGE。发现 1 Important + 3 Minor,当场在 4cd0081 修:
  - **Important**:文件工具错误契约不一致——ReadFileTool(T9 修过)返回 TOOL_ERROR,但 ListFilesTool/WriteFileTool 仍让 OSError 逃逸 run()。全分支视角才暴露(单 task 评审看不到)。三工具统一为 ToolResult(TOOL_ERROR)。
  - Minor:WriteFileTool 写入 pin encoding=utf-8(与 size check 的 encode 一致);ToolResult status/category 改 Literal 类型(拼写错误在校验期即报,SPEC §M9 八类 taxonomy,主循环靠它分支)。
  - +4 回归测试(list 缺目录、write 不可写路径、bad status、bad category)。48 passed。
- **延后(不阻塞)**:T6 Anthropic system=""(API 接受,won't-fix);_real_post 函数内 import(对离线确定性反而是优点);registry 注解(价值低)。
- **多轮记录/status 分类等覆盖建议**:opus 建议后续加 MockLLM 多轮 received_messages[2] 断言(demo② 依赖)——记入 M4 主循环时补。
- **人工干预**:控制器决定合并修 Important+2 Minor(错误契约是主循环安全网的关键一致性;Literal 让控制流 seam 防拼写错)。
- **下一步**:PR + merge;之后 Milestone 2(治理,main contribution)。

---

## 2026-07-14 · Milestone 2 启动(治理 — main contribution)
**Worktree**:`.claude/worktrees/m2-governance`,分支 `worktree-m2-governance`(base = main @ 43576ff,M0+M1 已并入)。基线 `make test` = 48 passed。
**模块**:T10 决策+引擎、T11 路径围栏(乙)、T12 受治理分发器、T13 命令词法(甲 1-2层)、T14 命令规则(甲 3-4层)、T15 审批状态机、T16 命令执行工具、T17 run_tests+finish。全部依赖已在 main。

### Task 10 · Decision + 有序 PolicyEngine — ✅ 完成 (5a6739d, +3c402ea)
- **TDD**:RED = 模块不存在;GREEN = 3 新测试,`make test` 51 passed。
- **产物**:aegiscode/governance/{__init__,decision.py,engine.py}。decision.py 纯 re-export config.schema.Decision(单一真源,test 断言 `Decision is ConfigDecision` 身份成立);GovernanceVerdict/PolicyRule dataclass;PolicyEngine.evaluate 有序 first-match-wins,无命中走 default_fn;每判定带 rule_id+reason。无具体规则(留给 T11/T13/T14)。
- **两阶段评审**:spec ✅、quality Approved。2 Minor:①matcher 异常未捕获(引擎骨架,交 T12 dispatcher 作 try/except 边界)②单规则 ordering 测试不足以证 first-match-wins。②加 2 规则 ordering 测试 3c402ea(52 passed);①carried 到 T12。
- **人工干预**:控制器决定补 ordering 测试(证治理核心不变量),matcher 异常 carry 到 dispatcher。

> 说明:T11–T17 原为一个塌缩汇总块,现按纪律补全为逐任务详细条目(基于 git 提交 + PLAN + 源码核验重建,非事后杜撰;所有 commit hash、文件、机制均经核对)。

### Task 11 · 路径围栏(乙)— realpath 归属 + 敏感文件黑名单 — ✅ 完成 (fd91949, +1cde65e, +b48f4a9)
- **产物**:新建 `aegiscode/governance/path_fence.py` + `tests/governance/test_path_fence.py`。`PathVerdict(NamedTuple: allowed:bool, reason:str)` + `check_path(path, workspace_root, sensitive_patterns) -> PathVerdict`。乙的核心机制:先 `realpath(workspace_root)` 冻结根;相对路径 join 到根、绝对路径原样;已存在目标(或本身是 symlink)→ `realpath` 整条解析,新文件 → 只 `realpath` 其**父目录**再拼 basename(否则不存在的路径 realpath 无意义);归属判定一律用 `os.path.commonpath([realpath(target), root]) == root` 而**非字符串前缀**;最后对 basename 做 `fnmatch` + 对路径分段做敏感目录匹配。Linux 语义。
- **TDD/测试**:RED = 模块不存在。首提 5 测试钉住:symlink→/etc/passwd 越界拒、`../../` 遍历拒、工位内新文件放行、`.env` 敏感拒、工位内绝对路径放行。
- **评审/修复**:
  - `1cde65e`(sibling-prefix 不变量):补 `test_sibling_prefix_dir_denied` / `test_traversal_to_sibling_prefix_denied`——`/ws` 与 `/ws-backup` 共享字符串前缀但是不同目录,证明必须用 `commonpath` 判定;若退回字符串 `startswith` 这两测试立刻变红。
  - `b48f4a9`(**CRITICAL**,M2 最终评审当场发现的符号链接绕过):原实现敏感模式只对**输入路径字符串** `path` 匹配。工位内一个无害命名的软链 `report.txt -> .env`(目标也在工位内)归属检查通过,却能读到 `.env`——黑名单被绕过。修复抽出 `_matches_sensitive(p, patterns)`,对**输入路径 AND 解析后 realpath 两者**都跑敏感匹配(fail-safe 叠加),并补 `test_symlink_to_sensitive_file_inside_workspace_denied` 回归。安全意义:归属通过 ≠ 内容安全,敏感判定必须落在解析后的真实目标上。
- **安全/SPEC**:落实 SPEC 决策 #13(乙 realpath 先于归属、commonpath 非前缀)。背书 demo ③ symlink escape——越界软链与工位内敏感软链两条路径都被 DENY。

### Task 12 · 受治理分发器 — 把路径围栏 + 默认档接进工具分发 — ✅ 完成 (c62f0e0, +e752c54)
- **产物**:新建 `aegiscode/governance/dispatcher.py` + `tests/governance/test_dispatcher.py`。`Dispatcher(registry, engine, path_config)`,`dispatch(action, ctx) -> (GovernanceVerdict, ToolResult|None)`。流水序:①未知工具 → `INVALID_ACTION` 结果、不执行;②文件类工具(`read_file/write_file/list_files/search_text`)带 `path` 参数 → 先跑 `check_path`,失败 → `DENY/PATH_FENCE` + `POLICY_DENIED`、不执行;③`engine.evaluate`;④DENY → verdict + `POLICY_DENIED`、不执行;⑤REQUIRE_APPROVAL → verdict + `None`(暂停交主循环);⑥ALLOW/ALLOW_WITH_AUDIT → 执行工具。围栏刻意排在策略引擎之前。
- **TDD/测试**:RED = 模块不存在。首提含未知工具→`INVALID_ACTION`、路径逃逸在执行前被 DENY,以及承接 T10 的 matcher 异常 guard(见下)。
- **评审/修复**:
  - 承接 T10 的健壮性:`engine.evaluate` 被包在 `try/except Exception` 内,任何 matcher 抛异常 → `DENY/INTERNAL_ERROR`,`test_matcher_exception_returns_internal_error` 用会爆的 matcher + spy 工具证明 `executed==[]`——策略代码 bug 也 fail-closed,绝不误放执行。
  - `e752c54`(no-exec spy 断言):补 `test_deny_from_policy_does_not_execute` 与 `test_require_approval_does_not_execute`,各用记录调用的 SpyTool 断言 DENY 与 REQUIRE_APPROVAL 两条路径 `executed == []`。把"判决即拦截、判决前工具零副作用"钉成不变量。
- **安全/SPEC**:确立 dispatcher 在 DENY / REQUIRE_APPROVAL / 围栏失败 / matcher 异常四种情形全部 no-exec 气密。是三演示共同的执行边界。

### Task 13 · 命令词法 + 结构安全层(甲,层 1–2)— ✅ 完成 (9f1b33c, +40bc08c)
- **产物**:新建 `aegiscode/governance/command_lexer.py` + `tests/governance/test_command_lexer.py`。`LexResult(NamedTuple: ok, argv, reason, has_metastructure)` + `lex_command(command) -> LexResult`。机制:先对**原始字符串**扫描元结构 token 集 `_META`,命中即 `ok=False, has_metastructure=True`(词法先于 `shlex`);无元结构才 `shlex.split`;shlex 失败(如引号未闭合)→ `ok=False`;空 argv → 拒。
- **TDD/测试**:RED = 模块不存在。首提钉管道 `|`、重定向 `>`、命令替换 `$(...)`、链接 `&&`、未闭合引号 → 拒。
- **评审/修复**:
  - `40bc08c`(**CRITICAL**,评审发现的注入缺口):初版 `_META` 遗漏了 glob 与换行,且列表有重复项(`$(` 出现两次)。修复重写为含 glob(`* ? [ {`)、追加重定向 `>>`、换行注入(`\n`/`\r`)的完整集,并去重 + 把多字符 token(`&&`/`||`/`>>`)排在单字符前避免顺序歧义(实测终态:`["&&","||","$(",">>","|",">","<",";","` "`" `","&","(",")","*","?","[","{","\n","\r"]`)。补 7 组测试:`rm *` glob、`file?.txt`/`[abc].py`、`echo safe\nrm -rf /` 换行注入、无空格 `echo hi|sh` / `a&&b` / `a;b`、反引号 `` `id` ``,以及纯命令仍 ok。安全意义:glob 与换行都能承载二次命令注入,缺任一项甲的结构层就有实洞。
- **安全/SPEC**:落实 SPEC 决策 #9(甲 词法先于 shlex、元结构集完整)。任何具 shell 元结构的命令在进入 argv 判定前即被拒,是 demo ① `rm -rf /` 被 DENY 的第一道闸(此处即被 glob/结构层拦下)。

### Task 14 · 命令白名单 + 危险参数规则(甲,层 3–4)— ✅ 完成 (85a1905, +839ceac)
- **产物**:新建 `aegiscode/governance/command_rules.py` + `tests/governance/test_command_rules.py`。`judge_command(command, allowlist, rules) -> GovernanceVerdict`。判定序:先 `lex_command`(元结构/词法失败 → `DENY/CMD_STRUCT`);`argv[0] not in allowlist` → `DENY/CMD_ALLOWLIST`;再遍历扁平规则 `{argv0, args_contain, decision}`,`argv0` 匹配且 `all(tok in args for tok in args_contain)` 首命中即返回其判决(`CMD_RULE_*`);否则 `ALLOW/CMD_DEFAULT_ALLOWED`。危险集 `sudo/su/rm/chmod/chown/curl/wget` 不写显式规则——它们因不在 allowlist 而落 DENY;显式规则覆盖 `git push`(DENY)、`git commit`(APPROVAL)、`pip install`(APPROVAL)、`python -c`/`python -m`(DENY)。
- **TDD/测试**:RED = 模块不存在。首提钉 `rm -rf /`→DENY、`pip install`→APPROVAL、`python -c`→DENY、`pytest -q`→ALLOW、不在白名单→DENY、管道→DENY。关键 `test_shipped_config_allows_pip_to_reach_approval`:直接从 `config.schema.Governance()` 代码默认(无 YAML、无手写镜像、无 `or RULES` 兜底)取 allowlist/rules,断言黄金路径 `pip install`→APPROVAL 且 `git push`→DENY——若有人清空默认规则或从白名单删掉 pip,此测试立刻红(呼应冷启动 D-CS8/D-CS15 教训)。
- **评审/修复**:`839ceac`(多 token ALL-match 边界):补 `test_multitoken_rule_requires_all_tokens`。新增 `git reset --hard`(DENY)规则后,`git reset --hard` 两 token 齐全 → 命中 DENY,而单独 `git reset` 只有一个 token → **不**命中,git 在白名单内 → ALLOW。证明 `args_contain` 是 all-of 语义而非 any-of,避免误伤安全子命令。
- **安全/SPEC**:落实 SPEC 决策 #9(甲 白名单 + 危险参数分档)。实测背书 demo ①:`rm -rf /` → DENY、`pip install` → REQUIRE_APPROVAL 均通过。

### Task 15 · 审批状态机(HITL)— ✅ 完成 (cedc259, +85f9ad3)
- **产物**:新建 `aegiscode/governance/approval.py` + `tests/governance/test_approval.py`。`ApprovalState(str,Enum)` = PENDING/APPROVED/REJECTED/EXPIRED/SUPERSEDED;`fingerprint(action)` = 对 `{tool, arguments}` 的 canonical JSON(`sort_keys=True`)取 SHA256;`@dataclass ApprovalRequest`(approval_id/task_id/step_index/action_snapshot/action_fingerprint/rule_id/reason/risk_explanation/state);`ApprovalStore` 提供 `create/get/decide(approved:bool)/remember(task_id,fp)/check_remembered`;`validate_resume(approved_fp, current_action)` 在 `fingerprint(current_action) != approved_fp` 时抛 `SupersededError`。
- **TDD/测试**:RED = 模块不存在。4 测试钉:指纹稳定且对参数变化敏感(`pip install x` ≠ `pip install y`);`decide(True)` → 状态转 APPROVED;`validate_resume` 在动作从 `pip install x` 变 `pip install evil` 时抛 `SupersededError`;`remember/check_remembered` 按 `(task_id, fp)` 记忆同一指纹。
- **评审/修复**:`85f9ad3`(style)删去未使用的 `field` import,保持 ruff 干净。核心机制无返工。
- **安全/SPEC**:落实 SPEC 决策 #14(HITL)。指纹 + `validate_resume` 背书 demo ④ SUPERSEDED——审批授予的是"当时那个动作"的指纹,恢复时动作若被改写则判 SUPERSEDED 而非沿用旧批准,杜绝"批一个、换着执行另一个"的越权。

### Task 16 · run_command 执行器(甲 层 5,shell=False)— ✅ 完成 (b64465b)
- **产物**:新建 `aegiscode/tools/command_tool.py` + `tests/tools/test_command_tool.py`。`RunCommandTool(allowlist, rules, timeout_sec, output_max_bytes)`,`run(arguments, ctx)`:`shlex.split` 成 argv 后 `subprocess.run(argv, shell=False, cwd=ctx.workspace_root, capture_output=True, text=True, timeout=...)`;`TimeoutExpired` → `TIMEOUT`;stdout+stderr 合并并按 `output_max_bytes` 截断;returncode≠0 → `status="failure"`。此工具只执行已被判定放行的 argv,治理判决本身由 dispatcher 经 `judge_command` 完成。
- **TDD/测试**:RED = 模块不存在。3 测试:`echo hello`→success 且输出含 hello;`python -c sys.exit(3)`→exit_code=3、failure(测试注明治理层本会在上游拦 `python -c`,此处只验执行语义);`sleep 5` 撞 1s timeout → `TIMEOUT`。
- **安全/SPEC**:落实甲的执行层 `shell=False` + 直传 argv——即使命令字符串带元字符也不会交给 shell 解释(与 T13 结构层双重保险)。M2 评审记的 char/byte 截断口径为良性 Minor,defer。

### Task 17 · run_tests 传感器 + finish 控制工具 — ✅ 完成 (93d1ca7)
- **产物**:新建 `aegiscode/tools/run_tests_tool.py` + `aegiscode/tools/finish_tool.py` + `tests/tools/test_run_tests.py`。`RunTestsTool(test_command, timeout_sec, output_max_bytes)`:执行**配置里固定的** `test_command`(`shell=False`,`cwd=ctx.workspace_root`),`run` 忽略传入 arguments,原样返回 `ToolResult`(失败分类留给 T18);`TimeoutExpired`→`TIMEOUT`。`FinishTool` 返回 `ToolResult(tool="finish", status="success", artifacts={"finish": True})`。
- **TDD/测试**:RED = 模块不存在。`test_runs_fixed_command` 在 tmp 工位写一个 `test_ok.py` 跑 `pytest -q` 断言 exit_code==0;`test_finish_flag` 断言 finish 工具的 `artifacts["finish"] is True`。M2 汇总记录 brief 里的 fixture 命名 bug `t_ok.py`→`test_ok.py`(否则 pytest 采集不到)已在本任务内修正。
- **安全/SPEC**:确立 run_tests 是"固定命令传感器"——测试命令由配置冻结,不可被 LLM 经 arguments 劫持成任意命令执行,是反馈回路的可信输入源;finish 仅表意愿,真正终止由主循环的 final_verifier 裁定(M4)。




### 全分支最终评审(Milestone 2,opus)— READY TO MERGE
- 安全评估:甲(词法先于 shlex、元结构集完整含 glob/newline)、乙(realpath 先于归属、commonpath 非字符串前缀)、dispatcher no-exec 在 DENY/APPROVAL/fence-fail/matcher-exception 全部气密、HITL 健全、零提示词安全。三演示①③④均有真实测试背书。
- **发现并当场修**:乙的敏感文件检查只查输入路径字符串,in-workspace 符号链接 report.txt->.env 可绕过黑名单(归属通过但读到 .env)。b48f4a9 修:敏感匹配同时对解析后 realpath 执行(fail-safe 叠加)+回归测试。94 passed。
- **两项 M4 强制跟踪项(不可遗漏)**:①judge_command 命令管线目前是 orphan——dispatcher 尚无 run_command→甲管线的分支;②config 驱动的 default_fn(readonly→ALLOW/write→APPROVAL/command→DENY)尚无组装。二者根因同:装配缝隙属 M4/T23。建议建 aegiscode/governance/factory.py(build_engine/build_default_fn),并加两个集成测试:(a)经 Dispatcher.dispatch 的 run_command "rm -rf /"→DENY no-exec;(b)write_file 越 allowlist→APPROVAL。评审判定 defer 合理(M2 是单元组合里程碑,无 harness 故非活漏洞)。
- 延后 Minor:T16 char/byte 截断(良性)、T17 arguments 忽略注释、readonly_tools 未被 dispatcher 消费(factory 统一)、ApprovalRequest 缺 §11.4 部分字段(TaskState 落地时补)、dispatcher/tool 两条路径解析需 M4 保证一致。
- **人工干预**:控制器当场修乙绕过(安全核心、fail-safe、单文件);其余按评审 defer 并记为 M4 硬性条件。
- 下一步:PR + merge;之后 Milestone 3(反馈/审计/记忆)。

---

## 2026-07-14 · Milestone 3(反馈/审计/记忆)— 新 worktree
**Worktree**:`.claude/worktrees/m3-feedback-audit-memory`,分支同名(base = main @ e143d34,M0+M1+M2 已并入)。基线 make test = 94。
**顺序**(依赖正确):T25 secret scanner(先做,解锁 T20)→ T18 反馈分类 → T19 审计哈希链 → T20 记忆存储 → T21 上下文构建。实现/评审 sonnet(1 处 haiku 微改),最终评审 opus。

> 说明:T25 及 T18–T21 原为塌缩 bullet(违反工作流 #11 逐任务记录纪律),现按纪律补全为逐任务详细条目(基于 git 提交 + PLAN + 源码核验重建)。参见记忆 per-task-agentlog-discipline。

### Task 25 · 自写密钥扫描器(CI + 自检)— ✅ 完成 (b39c3ca, +f271fd7)
- **依赖序**:先于 T20 做——T20 记忆 write 复用其 `scan_text` 做写前密钥拒绝。
- **产物**:`aegiscode/credentials/scanner.py`。`_PATTERNS` 4 类确定性正则:`sk-ant-[A-Za-z0-9\-_]{20,}`(Anthropic)、`sk-[A-Za-z0-9]{20,}`(OpenAI)、`AKIA[0-9A-Z]{16}`(AWS)、`(?i)(KEY|TOKEN|SECRET|PASSWORD)\s*=\s*[A-Za-z0-9\-_+/=]{16,}`(通用赋值)。`@dataclass Finding(path, line_no, pattern)`;`scan_text(text, path)` 逐行逐模式匹配返回 Finding 列表;`scan_paths(paths)` 遍历文件(`errors="ignore"`)。与 M0 redactor 共用同一批 key 模式(评审记为 pattern-drift 应合并单一源的跟踪项)。
- **TDD/测试**:RED = 模块不存在。测试钉:植入 `sk-…` 被检出且带 pattern、干净文本零发现、`scan_paths` 命中文件正确行号。
- **评审/修复(f271fd7)**:修 `scan_paths` 的 `open()` 文件句柄泄漏——改用 `with` 上下文管理器确保句柄关闭。
- **安全/SPEC**:兑现 SPEC 决策 #18 的密钥扫描防线——确定性、可离线单测(§A.4C);既作 T20 记忆写前闸,又在 T32 被 CI secret-scan job 复用(scoped 到 shipped surface + allowlist)。

### Task 18 · 反馈分类 + pytest 摘要 + 无进展指纹 — ✅ 完成 (c0df597, +422f0f8)
- **产物**:`aegiscode/feedback/classifier.py` + `aegiscode/feedback/pytest_parser.py`。`classify(tr)` 消费 `ToolResult`,先透传已带失败 `category` 的类(POLICY_DENIED/INVALID_ACTION/TIMEOUT/TOOL_ERROR/APPROVAL_REJECTED/INTERNAL_ERROR/NO_PROGRESS),再由 `tool=="run_tests" and status=="failure"` 派生 TEST_FAILURE、其余 failure/error 归 TOOL_ERROR,成功返回 `None`(合 8 类失败空间,SPEC §M9)。`summarize_pytest(raw)` 只保留失败名 + `E ` 断言行 + 末 20 行 traceback,经 `dict.fromkeys` 去重保序。`ProgressTracker(window=3)` 用 `deque(maxlen=3)` 滑窗,`seen(fp)` 命中即返回 True——只拦完全重复的动作指纹(K=3),不臆测语义相似。
- **TDD/测试**:RED = 模块不存在。测试钉:`classify` 对 run_tests 失败 → TEST_FAILURE、denied → POLICY_DENIED;`summarize_pytest` 在噪声中仍保留失败名与断言行且行数受限;`ProgressTracker` 首见 False、再见 True。
- **评审/修复(422f0f8)**:两处修正——`classify` 返回注解由 `str` 收窄为 `str | None`(成功路径返回 None,注解与实现对齐);`summarize_pytest` 加硬上界 `[:40]`,防对抗性巨量 `E ` 断言行撑爆回灌;补 `test_summarize_pytest_is_hard_bounded`(100 行 E 断言 → 输出 ≤ 40 行)钉死不变量。
- **安全/SPEC**:兑现 M9 反馈闭环确定性——分类纯规则无 LLM;pytest 摘要行数硬有界(截断回灌);无进展检测严格为完全重复指纹 K=3,不做语义猜测。

### Task 19 · 审计事件 + SHA256 哈希链 + verify_chain — ✅ 完成 (af405cf, +8c36acb, +7f1477d)
- **产物**:`aegiscode/audit/events.py`(`EventType(str,Enum)` 7 类:ACTION_PROPOSED/GOVERNANCE_DECISION/APPROVAL_REQUESTED/APPROVAL_DECIDED/TOOL_EXECUTED/FEEDBACK/TERMINATION)+ `aegiscode/audit/chain.py`。`AuditLog(conn).append()` **写前先 `redact` 脱敏** payload_json,再取 `_prev_hash`(该 task 最后一行 hash,首条为 `GENESIS = "0"*64`),`hash = SHA256(prev ‖ 规范化 body)`(body 为 sort_keys 的 task_id/step_index/event_type/timestamp/payload_json),参数化 INSERT。`verify_chain(task_id)` 从 GENESIS 起逐行重算,`stored_prev != prev or stored_hash != h` 即返回 `(False, step_index)` 定位断点,全绿返回 `(True, None)`。
- **TDD/测试**:RED = 模块不存在。初始测试钉链可校验、篡改 payload → 定位、payload 写后脱敏(`sk-abcdef…` 不落库)。7f1477d 补三类篡改测试:hash 变异、行删除(破坏 running prev-hash 链)、多次 append 后链仍整。
- **评审/修复**:8c36acb 修 `datetime.utcnow()` 弃用 → `datetime.now(timezone.utc)`。7f1477d 在 `append` 显式 `commit()` 保证持久。**M3 最终评审 CHANGES-REQUIRED(e529ea8)**:纯前缀重算无法检测**尾部截断**(删最后一行后前缀仍自洽)——`verify_chain` 加可选 `expected_count` 计数锚,walked 行数 ≠ 期望即返回 `(False, rows_walked)`;补测试证明删尾行时朴素 verify 仍 `(True, None)`(文档化的已知限制,完整签名按 §M8 延后),带 `expected_count` 锚点则捕获。
- **安全/SPEC**:兑现 M8 篡改可检测 + 写前脱敏——payload 入库即脱敏,SHA256 前缀链定位首个断点,截断由计数锚兜底;明确只做可检测篡改、不做 HMAC 签名(未来项)。

### Task 20 · 记忆存储(拒密钥写入 + 过滤检索)— ✅ 完成 (738ad8a, +ce70499)
- **产物**:`aegiscode/memory/store.py`。`MemoryStore(conn).write(project_id, type, key, value, tags, source, confirmed=None)` 写前调 `scan_text`(复用 T25 `aegiscode/credentials/scanner.py`,b39c3ca)命中密钥即返回 `None` 拒写;`source=="agent"` 强制 `confirmed=False`,否则默认 `True`;`uuid4` 主键、时区感知 UTC 时间戳、参数化 INSERT(无注入)。`retrieve(project_id, query=None, top_k=8)` 按 `project_id` 过滤 + 可选关键词 `LIKE`(key/value/tags_json)+ `ORDER BY last_used_at DESC LIMIT top_k`,命中行 bump `use_count`/`last_used_at`。`is_governance_usable(row)` 静态判定 `source != "agent"`——Agent 记忆永不作治理依据。
- **TDD/测试**:RED = 模块不存在。初始测试钉:拒写密钥 value、关键词检索命中、agent 记忆 `confirmed==0` 且 `is_governance_usable` 为 False、topK 上限(12 写入 → 检索 8)。ce70499 补跨项目隔离(`test_retrieve_is_project_scoped`):p1/p2 各写一条,检索互不串;关键词搜也不跨项目。
- **评审/修复**:**M3 最终评审 CHANGES-REQUIRED(e529ea8)**——① `retrieve` 缺 `type` 过滤(SPEC §M10 要求 type+project+关键词+topK),补 `type=None` 参数与 `AND type=?` 分支及 `test_retrieve_filters_by_type`;② 脱敏只扫 value 有漏——`write` 扩为 `scan_text(value) or scan_text(key) or scan_text(" ".join(tags))`,补 `test_write_refuses_secret_in_key_or_tags`(密钥藏 key 或 tags 均拒写)。
- **安全/SPEC**:兑现 M10——写入过脱敏器(密钥在 value/key/tags 任一位置皆拒)、source=agent 永不治理可用、检索严格 project 隔离(无跨项目泄漏)、全参数化 SQL。

### Task 21 · 上下文构建(6 段预算装配 + 确定性摘要)— ✅ 完成 (932e893, +b633118)
- **产物**:`aegiscode/memory/context_builder.py`。`build_context(system_prompt, tool_protocol, task, recent_steps, last_feedback, memories, budget_chars)` 按优先级装配 messages:① system + 工具协议 ② TASK ③ recent steps(newest-last 明细)④ 最新反馈 ⑤ 记忆 top-k ⑥ 代码片段。超 `budget_chars` 时**从最旧轮起**用 `summarize_step(step)` 有损摘要化(仅留 `tool`/`governance_decision`/`feedback_category`,丢 detail)——**零 LLM、纯确定性**,head(system 段)永不进入摘要/丢弃循环。
- **TDD/测试**:RED = 模块不存在。测试钉:`summarize_step` 确定性且有损(含 tool 与 feedback_category、剔除大段 detail、两次调用相等);预算触发摘要后总字符有界且 system 段仍在。b633118 补 `test_feedback_precedes_memories_in_order`(反馈内容下标 < 记忆内容下标)。
- **评审/修复(b633118)**:修 tier 顺序——原实现记忆(tier 5)排在反馈(tier 4)之前,违反 SPEC 优先级;调整为反馈先于记忆装入 tail 并补序测试钉死。
- **安全/SPEC**:兑现 M10 上下文段——6 段优先级装配 + 字符数近似预算 + 超预算确定性摘要化最旧轮(不调 LLM),system-constraints 段任何情况下不被丢弃。


### 全分支最终评审(Milestone 3,opus)— CHANGES REQUIRED → 已解决(e529ea8)
- **阻断**:retrieve 缺 type 过滤(SPEC §M10/§14 验收明列 type+project+keyword+topK)。已补可选 type 参数 + AND type=?。
- **Important**:审计尾部截断不可检测(删末尾行留下合法前缀,verify_chain 仍报 intact)。已加 verify_chain(expected_count) 计数锚点 + 文档说明(完整签名按 §M8 延后)。
- **安全**:记忆 write 现对 value+key+tags 都 scan_text(key 在检索面上)。
- e529ea8 修全部三项 +3 测试,119 passed 且 -W error::DeprecationWarning 纯净。
- **跟踪(非阻断,带入后续)**:scanner(T25)与 redactor(M0)重复维护 key 模式列表(今日完全一致,应合并单一源防漂移);is_governance_usable 仅咨询性,M4 主循环须逐行调用;classify 测试仅覆盖 8 类中 2 类(M4 接线时补)。
- **人工干预**:控制器判定 type 过滤为阻断(书面验收未达)、尾部截断锚点与 key/tags 扫描当场折进一个修复提交;pattern-drift 合并 defer。
- 下一步:PR + merge;之后 Milestone 4(主循环 T22 停机 + T23 HarnessCore,含 M2 遗留的治理 factory 装配硬性条件)。

---

## 2026-07-14 · Milestone 4(核心主循环)— 新 worktree
**Worktree**:`.claude/worktrees/m4-core-loop`,分支同名(base = main @ 9dd51f8,M0+M1+M2+M3 已并入)。基线 make test = 119。
**顺序**:T22 停机逻辑 → 治理 factory(M2 遗留硬性装配)→ T23 HarnessCore 主循环。实现/评审 sonnet,最终评审 opus。**纪律**:每个 task 完成即写本文件的 `### Task N` 条目 + PLAN 标记 + 账本行。
**M2/M3 带入的硬性条件**:①factory 把 run_command→judge_command 与 config 驱动 default_fn 接进 dispatcher + 2 个 Dispatcher.dispatch 级集成测试(rm -rf DENY no-exec / write 越 allowlist REQUIRE_APPROVAL);②主循环消费记忆时逐行调用 is_governance_usable。

### Task 22 · 停机原因 + 优先级判定 — ✅ 完成 (7b63874, +69867d7)
- **技能**:subagent-driven-development;实现/评审 sonnet。
- **TDD**:RED = 模块不存在;GREEN = 6 新测试,make test 125 passed。
- **产物**:aegiscode/loop/{__init__,termination.py}。TerminationReason(str,Enum) 9 值;LoopCounters(step/consecutive_failures/invalid_actions/no_progress_hits);decide_termination 计数档优先级 INVALID_ACTION_LIMIT>CONSECUTIVE_FAILURES>NO_PROGRESS>MAX_STEPS,健康返回 None;非计数档(COMPLETED/FINISH_REJECTED/LLM_ERROR/INTERNAL_ERROR/CANCELLED)由主循环直接设置。
- **两阶段评审**:spec ✅、quality Approved。2 Minor(缺返回注解、无同时触限的优先级测试)在 69867d7 修复 + 优先级测试,126 passed。
- **人工干预**:控制器补返回注解与优先级断言(证计数档优先级不变量)。注:此 task 的 fix/PLAN/log 曾因工具输出中断丢失,恢复工具后重做并核实真实提交状态,未重复已完成实现。

### Governance factory · M2/M3 遗留装配硬性条件 — ✅ 完成 (11c5bea, +ff13ed5)
- **技能**:subagent-driven-development;实现/评审 sonnet;人工补丁一处(尾斜杠归一化)。
- **背景**:M2 最终评审判定并非活漏洞而是装配缝隙,defer 到 M4,并列为硬性 M4 前置。此为本项落地。
- **TDD**:RED = 模块不存在;GREEN = 18 新测试,144 total;补 1 归一化回归测试后 19/145。
- **产物**:aegiscode/governance/factory.py。4 个构建器:build_default_fn(config)/build_engine(config)/build_path_config(config)/build_dispatcher(config, registry)。default_fn 分档:run_command→judge_command(动态);finish→ALLOW(TIER_FINISH);readonly {read_file,list_files,search_text}→default_decisions.readonly(TIER_READONLY);write_file→在 write_allowlist_dirs 前缀内→ALLOW(TIER_WRITE_ALLOWLISTED),否则→default_decisions.write(TIER_WRITE);兜底→default_decisions.command(TIER_DEFAULT,fail-closed 默认 DENY)。命令走 judge_command 全流水线保留 甲(1-4)。
- **M2 硬性 2 集成测试**:test_dispatch_rm_rf_denied_no_exec(甲 → DENY,spy.executed==[]);test_dispatch_write_outside_allowlist_requires_approval(write_file→REQUIRE_APPROVAL,result=None,spy.executed==[])。两条 no-exec 由 spy 工具证实。
- **两阶段评审**:spec ✅、quality Approved。1 Important 归一化尾斜杠(否则 "src" 会误匹配 "src_evil/x.py")在 ff13ed5 修 + 回归测试证 "src" 归一化后拒 src_evil/。
- **人工干预**:控制器编写此非编号任务的 spec 文本(基于 M2 tracked 条件);手动补丁 write_allowlist_dirs 归一化(单行、fail-safe、单文件);其余产出由 subagent 完成。
- **PolicyEngine.rules=[]**:所有治理经 default_fn。留 seam 供未来自定义 PolicyRule。

### Task 23 · HarnessCore 主循环(集成)— ✅ 完成 (1632c54, +7b7dbe4)
- **技能**:subagent-driven-development;实现 sonnet(中途 API JSON 解析错误,续传完成);评审 sonnet;修复 sonnet 含控制器手工检查 spec §6 + 确认 FINISH_REJECTED 语义。
- **TDD**:RED = 模块不存在(tests/helpers.py + tests/loop/test_harness.py import harness);GREEN = 两个 demo 测试 +3 修复测试,make test 150 passed。
- **产物**:
  - aegiscode/loop/harness.py — HarnessCore 类。自研 while 循环(无 Agent SDK)。逐轮: build_context → llm.complete (retry llm_max_retries=3 from config) → parse_action (fail→INVALID_ACTION 反馈+审计+计数→ decide_termination) → audit ACTION_PROPOSED → progress check → dispatch → audit GOVERNANCE_DECISION → 按 verdict 分支:
    - DENY → audit FEEDBACK(POLICY_DENIED) +consecutive_failures +step continue(无 TOOL_EXECUTED)。
    - REQUIRE_APPROVAL → approval_resolver → approve: execute_approved (含路径护栏); reject: APPROVAL_REJECTED 反馈。
    - ALLOW/ALLOW_WITH_AUDIT → audit TOOL_EXECUTED → classify feedback → progress 计数。
    - finish → final_verifier(): pass → COMPLETED(唯一终止); fail → FINISH_REJECTED feedback, continue(撞上限转 MAX_STEPS per SPEC §6)。
  - aegiscode/governance/dispatcher.py 增 execute_approved(路径护栏+工具执行)。
  - aegiscode/config/schema.py Limits 增 llm_max_retries=3。
  - tests/helpers.py (make_harness 工厂,MockLLM+真治理+spy 审计/工具)。tests/loop/test_harness.py (demo1+demo2+finish_rejected_continues+deny_no_tool_executed 等)。
- **两阶段评审**:spec PARTIAL/质量 Needs Fixes(见下)。
  - Critical:DENY 路径错误地审计了 TOOL_EXECUTED(从未执行的动作)。
  - Important/安全:execute_approved 未检路径护栏(已审批不等于绕过工作区边界)。
  - SPEC 偏差:FINISH_REJECTED 曾直接返回终止(§6 要求回灌继续)。
  - Config 耦合:llm_max_retries 硬编码 3(已改读配置)。
  - 以上四项在 7b7dbe4 全修,150 passed 纯净。
- **人工干预**:控制器发现 subagent API 错误,检查磁盘产物,确认可续;亲读 §6 +dispatcher 确认 FINISH_REJECTED 语义为"反馈继续"而非"终止";在修复工单中注入这一条;其余由续传 subagent 完成。
- **MockLLM 离线确定性**:全部 demo 测试用 scripted MockLLM,零网络/零真 LLM。

### M4 全分支最终评审(opus)— CHANGES REQUIRED → 已解决 (12f13fd)
- **Critical 1**:governance factory 无 run_tests 分支 → 落入 TIER_DEFAULT → DENY。但 SPEC §6 明列 run_tests 为"反馈传感器",必须能执行。修:在 build_default_fn 加 TIER_SENSOR 分支,run_tests → ALLOW。
- **Critical 2 / 测试戏剧**:demo2 断言 `"fail" in m.lower()` 被 POLICY_DENIED 反馈里的"fail-closed"字面命中而通过,掩盖了 Critical 1。修:去掉 or 分支,断言 `"TEST_FAILURE" in m`;增补 `spy.run_tests_executions >= 2`(证传感器真跑了)与 round-2 FEEDBACK 事件 category==TEST_FAILURE(证真机制)。修 C1 后 demo2 因正确原因通过。
- **Important 3**:INTERNAL_ERROR 已定义但从未被设置。修:run() 每轮包 try/except Exception → audit + return INTERNAL_ERROR(fail-safe,不允许 run() 崩溃调用方);新增故意抛异常 dispatcher 的测试证实。
- **Important 4**:CANCELLED 无机制 + 记忆 TODO 只在 AGENT_LOG 未在源码。修:构造函数接受 cancel_check callable,循环首行检查,置 CANCELLED audit + return;记忆 TODO 已加到 build_context 调用处,为 T26 ApplicationService 留 seam。
- 12f13fd 一提交合修四项,153 passed,`-W error::DeprecationWarning` 纯净。
- **人工干预**:控制器直接验证 C1(python3 -c 复现 run_tests→DENY),读 SPEC §6 line 126 确认 run_tests 传感器身份,注入修复工单;C2 靠人工阅读 demo2 与 helpers 交叉核实"fail-closed"字面误命中假设并要求同时收紧断言 + 加真实执行 spy 证据。
- **跟踪(后续)**:approval_resolver 是同步回调,不足以承载 §6 "审批暂停+持久化+跨界恢复",T26 ApplicationService 需要 resume-capable entry(非阻塞式);memory 集成本身仍是 TODO(仅接进 seam,retrieve 未调用)。

---

## 2026-07-14 · Milestone 5(凭据)— 新 worktree
**Worktree**:`.claude/worktrees/m5-credentials`,分支同名(base = main @ f252662,M0-M4 已并入)。基线 make test = 153。单任务里程碑(T25 scanner 已在 M3 落地)。实现/评审 sonnet。

### Task 24 · 凭据存储(keyring→.env→env,fail-safe)— ✅ 完成 (d2bbb6f, +16c801d)
- **技能**:subagent-driven-development;实现/评审 sonnet。
- **TDD**:RED = 模块不存在;GREEN = 4 mandatory verbatim + 6 robustness 测试;修复后 12 store 测试,165 total 纯净。
- **产物**:aegiscode/credentials/store.py(与 M3 的 scanner.py 同包,未改动 scanner)。CredentialStore(backend, allow_dotenv=False, env=None, dotenv_path=None):set_key/clear(吞后端异常 fail-safe)/get_key(读序 keyring→.env 仅当 allow_dotenv→env,后端异常穿透下层)/status({configured, masked} 永不明文)。.env 默认关闭。env 默认 {} 不读 os.environ 防环境泄漏。
- **两阶段评审**:spec ✅、quality Needs Fixes。
  - Important/安全:掩码 v[:3]+…+v[-4:] 对 len<=7 的 key 完整泄漏(prefix+suffix 可重建),且原测试 'key not in str(st)' 因中间的 … 而误通过。修:len<8 → '***' 全遮;len>=8 → 'sk-…7890'。
  - Minor:.env 值未剥引号(OPENAI_API_KEY="x" 会带引号)。修:strip 引号。
  - 16c801d 合修 + 边界测试(7 字符→***,8 字符→前后缀式)。
- **人工干预**:控制器在评审前用 python3 -c 复现短 key 掩码泄漏(set_key('xy')→'xy…xy'),将其作为重点交给评审并要求测试改为断言 '***' 而非弱断言;确认真 OpenAI key(~51 字符)不受影响但安全组件不应泄漏任何短密钥。
- **验证**:xy/sk-1234→'***';sk-12345→'sk-…2345';sk-abcdef1234567890→'sk-…7890';全部 leak=False。
- 下一步:PR + merge;之后 Milestone 6(服务/接口:T26 ApplicationService → T27 FastAPI → T28 WebUI / T29 CLI)。

---

## 2026-07-14 · Milestone 6(服务/接口)— 新 worktree
**Worktree**:`.claude/worktrees/m6-service-interface`,分支同名(base = main @ cc5d867,M0-M5 已并入)。基线 make test = 165。链:T26 ApplicationService(+repositories)→ T27 FastAPI(8 端点)→ T29 CLI;T28 WebUI 依赖 T27。实现/评审 sonnet,最终评审 opus。每任务扩展 tests/helpers.py(T26 加 make_service,T27 加 make_api_client)。

### Task 26 · ApplicationService(创建/查询/审批/取消 + 持久化)— ✅ 完成 (f4ee46c, +ce96821)
- **技能**:subagent-driven-development;实现/评审 sonnet。
- **TDD**:RED = 模块不存在;GREEN = 15 新测试,180 total;修复后 +2 async 测试,182 total 纯净。
- **产物**:aegiscode/service/app_service.py + aegiscode/persistence/repositories.py + tests/helpers.py 加 make_service(sync 参数)。ApplicationService(db, db_path, config, harness_factory, sync=False):create_task(uuid,插 RUNNING 行,sync 内联/否则后台线程,跑 HarnessCore,按 TerminationReason 更新 COMPLETED/CANCELLED/FAILED)/get_task/get_events(since 严格 >N)/list_approvals/decide(approval_id,approved)/cancel/get_audit(verify_chain 元组解包 → chain_valid)。step 行由 run 后投影 audit_events(HarnessCore 未改)。参数化 SQL 无注入,schema.sql 未动。
- **审批暂停/持久化/恢复(T23 遗留 seam 落地)**:REQUIRE_APPROVAL → 插 PENDING approval_requests 行 → 暂停 → decide() 更新状态并唤醒 → resolver 返回 approved → 循环 execute_approved。sync 模式用注入的 sync_decision_fn 确定性判定;async 用 threading.Event。
- **两阶段评审**:spec ✅、quality Approved-with-caveats。
  - Important:async resolver 存在 lost-wakeup 窗口(先插行后注册 Event,decide 可能错过)+ ev.wait 无超时(永久挂起)。修:_approvals_lock 保护;Event 先于插行注册;ev.wait 有界超时(approval_timeout_sec 或 3600s)超时 fail-closed → REJECTED;唤醒后重读 DB 状态。
  - Important:make_service async 路径 AuditLog 仍包主线程连接(跨线程 sqlite 误用)。修:harness_factory 接 audit_conn,async 传 thread_conn,sync 传主连接。
  - Minor:approval 行 step_index 硬编码 0。修:AuditEventRepository.latest_action_step_index 取真实 ACTION_PROPOSED step。
  - Minor:approval_decisions 泄漏到生产构造函数。修:移除,改注入 sync_decision_fn(测试作用域)。
  - ce96821 合修四项 + 2 async 测试(pause/resume 跨线程 + decide-before-wait 仍唤醒),async 测试 5s 硬上限轮询跑 5 次零 flaky。
- **人工干预**:控制器判定 async 路径 bug 虽 M6 测试不触发但 T27 API 会以 async 驱动,升级为 must-fix(而非 defer);要求补真实跨线程 pause/resume 测试并加硬超时防 CI 挂起。
- **安全**:参数化 SQL;后台线程各开自己的 DB 连接。

### Task 27 · FastAPI REST(8 端点)— ✅ 完成 (b622087, +2781e8a)
- **技能**:subagent-driven-development;实现 sonnet,两阶段评审 sonnet。
- **TDD**:RED = api.py 不存在,21 测试全红;GREEN = 实现后 21/21 绿,203 total。polish 后 22 测试、204 total、ruff 干净、全离线(MockLLM + tmp sqlite,`sync=True`)。
- **产物**:`aegiscode/service/api.py` — `build_app(service, credential_store=None) -> FastAPI`,8 端点(SPEC §13 M13):POST /tasks · GET /tasks/{id} · GET /tasks/{id}/events?since=N · GET /tasks/{id}/approvals · POST /approvals/{id}/decision · POST /tasks/{id}/cancel · GET /tasks/{id}/audit · GET /credentials/status。未知 task 走 HTTPException 404;decide/cancel 对未知 id 返回 200 no-op(与 ApplicationService 语义一致)。`tests/helpers.py` 加 `make_api_client`(TestClient over build_app,sync=True service),供 T28 复用。
- **安全**:API 无鉴权、仅 localhost — 模块 docstring 明确警告不得暴露到公网。`/credentials/status` 仅回显 masked,永不明文(专门的明文泄漏测试)。全局 `@app.exception_handler(Exception)` → 通用 500 `{"detail":"internal error"}`,服务端记日志,响应体不泄漏 traceback/db 路径/config(注入 `sqlite3.OperationalError("SECRET_DB_PATH=...")` 的真实泄漏测试断言无 `Traceback`/`OperationalError`/`SECRET_DB_PATH`)。
- **polish(2781e8a)**:db.py 加 `check_same_thread=False` 的 doc 注释(Starlette 线程池路由同步端点必需;WAL+autocommit + 后台线程各开自己连接,单用户 localhost 下安全);清理 credential-leak 测试残留的复制粘贴断言;移除未用 `import pytest`。确认 pyproject filterwarnings 路径 `starlette.exceptions.StarletteDeprecationWarning` 为正规模块(`__module__` 实测),且该类非 `DeprecationWarning` 子类,`error::DeprecationWarning` 本不会升级它。
- **两阶段评审**:Stage1 SPEC 合规 ✅(8 端点齐全、masked-only、404 语义、错误不泄漏、离线确定性);Stage2 质量 — 0 Critical / 0 Important。Minor:默认 null-store 在真实 env key 存在时仍报 configured=False(fail-safe,不泄漏,建议 T28 入口注入真实 store);cancel/decide 端点测试薄但诚实(sync 下任务已完成,真实行为由服务层测试覆盖);report 计数漂移 21→22。均不阻塞。
- **人工干预**:控制器补跑正式两阶段评审(前次仅有 report 无 review),确认 filterwarnings 路径实为正确(推翻上下文中"路径错误"的假设);移除未用 import 使 ruff 干净。

### Task 28 · WebUI(原生 静态 + 轮询)— ✅ 完成 (84cd1b2, +a4db1c2, +3bfa682)
- **技能**:subagent-driven-development;实现 sonnet,两阶段评审 sonnet,fix sonnet。
- **TDD**:RED = `/`、`/app.js`、`/style.css` 未挂载,5 红 1 绿;GREEN = 挂载后 6/6 绿,210 total;diff 修复后 +3 测试,213 total;kernel F841 清理后仍 213 绿、ruff 干净。全离线(TestClient over MockLLM service)。
- **产物**:`aegiscode/service/webui/{index.html,app.js,style.css}`(原生 HTML/CSS/JS,无框架/CDN/构建步骤)+ `aegiscode/service/api.py` 加 3 条显式 `FileResponse` 路由(`GET /` → text/html、`/app.js` → application/javascript、`/style.css` → text/css;`Path(__file__).parent/"webui"` 定位,CWD 无关,不与 8 个 JSON 端点冲突)。单页:workspace+描述→`POST /tasks`;`setInterval` 1500ms 轮询 `events?since=<水位>`(水位取 max event_id,严格 `event_id > since` 无 off-by-one)、approvals、task;审批面板 approve/reject → `POST /approvals/{id}/decision`;审计 Verify-chain → `GET /audit` 显示 `chain_valid`;终态(COMPLETED/FAILED/CANCELLED)停止轮询。`tests/service/test_webui_served.py` 6→ 后续 +1 = 相关测试。
- **安全 / XSS**:所有服务端字符串经 `textContent`/`JSON.stringify` 注入,`innerHTML` 仅用于 `= ""` 清空 → 恶意 workspace 路径/任务描述不被解释为 HTML。凭据指示仅消费 `/credentials/status`(masked),无新增明文面;无新增鉴权面(仅静态资源路由,localhost-only 姿态不变)。
- **两阶段评审**:Stage1 SPEC 合规 — 资产服务、字段名与 schema 全对齐、水位正确、轮询无泄漏、native-only、masked-only 均 PASS。Stage2 质量 — 0 Critical。**1 Important**:`renderDiff` 为死代码 / 未满足 SPEC §13「diff 必做」— TOOL_EXECUTED 审计 payload 仅 `{tool,status}`,丢弃 `result.artifacts`,故 changed_files 永不到达 UI。Minor:poll 无重入守卫(localhost 单用户无害)、brief 提及的 README 手测步骤未写、step_count 运行中显示 0。
- **Important 修复(a4db1c2,TDD)**:harness.py 在 TOOL_EXECUTED 追加 `changed_files`(仅当 `result.artifacts.get("changed_files")` 真值时,写工具有、run_tests/finish 无噪声键);payload 经 `redact` + 哈希,不改 schema/哈希/脱敏;`verify_chain` 不受影响(哈希动态计算无 golden)。app.js `renderDiff` 改为读 `payload.changed_files`,非空数组时渲染「changed files (N)」列表,逐条经 `textContent`(XSS 安全)。+2 harness 测试(写工具有键 / 只读工具无键)+ 1 WebUI 测试(app.js 含 changed-files 渲染逻辑)。全文本快照 diff 仍延后至 v2(SPEC line 113 写前快照 = SHOULD)。
- **人工干预**:控制器核实 Important 属实(SPEC §13 line 257「diff 必做」),判定为在范围内的 v1 合规缺口而非可延后项 → 派 fix subagent 以 TDD 打通 artifacts→审计→WebUI 数据链;另清理 kernel 预存 F841(harness.py:79 未用 `exc` 绑定,3bfa682)使治理内核 ruff 干净。

### Task 29 · CLI(init/run/serve/config/key/demo)+ 生产装配 + 凭据后端 — ✅ 完成 (95863ad, +09f1420)
- **技能**:subagent-driven-development;实现 sonnet,两阶段评审 sonnet,修复 sonnet。
- **TDD**:RED = `aegiscode.cli` 不存在;GREEN = 13 CLI 测试绿,226 total;评审修复后 +5 测试,231 total,ruff 干净,全离线(MockLLM + 猴补 uvicorn.run,零网络零绑定)。
- **产物**:
  - `aegiscode/cli.py` — `main(argv) -> int` argparse 分发六子命令。`init` 脚手架 aegis.yaml(往返有效);`config` 校验+打印,ConfigError/OSError → rc=2;`key set|status|clear`(set 用 getpass,永不回显明文;status 复用 `CredentialStore.status()` 掩码);`run --workspace --task [--watch]`(sync=True 保证进程退出前到终态);`serve`(sync=False 后台线程,localhost-only);`demo`(最小 MockLLM 零网络治理 DENY 演示,非 T31 四演示套件)。
  - `aegiscode/service/assembly.py` — **全系统首次真实装配**:`build_service(config, credential_store, db_path, sync)` + `build_llm(config, key)`(mock/openai/anthropic 分发,无 key → NoKeyError → CLI 友好非零退出)+ 真实 `ToolRegistry`(仅 `config.tools.enabled`)+ 真实 dispatcher + 真实 `final_verifier`(复跑反馈命令,COMPLETED 由验证器绿而非 LLM 声称)。`harness_factory` 五参签名与 ApplicationService 两处调用点精确匹配;跨线程 sqlite 干净(async 各开自己连接,audit 建在 audit_conn 上)。
  - `aegiscode/credentials/backend.py` — `build_credential_store(env)`:AEGIS_HOME → JSON 文件后端(测试可 hermetic + keyring 不可用降级),否则 keyring(`except Exception` 降级到 `~/.aegiscode` JSON)。复用 CredentialStore 掩码。
- **两阶段评审**:Stage1 SPEC 合规 — 六子命令齐全、key 不泄漏明文、自实现 harness(无 SDK)、离线确定性 均 PASS。Stage2 质量 — **1 Critical + 2 Important**,已全部修复:
  - **C1(CRITICAL,治理主场维度)**:路径围栏锚定 `config.workspace.root`(dispatcher 构建时冻结,默认 `/workspace`)而非每任务 `ctx.workspace_root`。测试中两者相等故未暴露;主机 `run --workspace X` / `serve`(每请求 workspace)路径下两者发散 → 工位内 `report.txt → .env` 软链绕过围栏(**回退了 b48f4a9 的软链修复**)。修:`dispatch()` 与 `execute_approved()` 均改 `root = getattr(ctx,'workspace_root',None) or pc.workspace_root`,`path_fence.py` 算法未动。**控制器独立复现**:发散根 + 工位内软链 → 修复后 DENY/PATH_FENCE、status=denied、secret 未泄漏(非测试戏法)。
  - **I1**:凭据文件 chmod-after-write 存在 world-readable 窗口。修:`os.open(path, O_WRONLY|O_CREAT|O_TRUNC, 0o600)` 创建即受限。
  - **I2**:凭据父目录 world-traversable。修:`os.makedirs(d, mode=0o700, exist_ok=True)` + 兜底 chmod。
  - Minor(未阻塞):`serve --host 0.0.0.0` 仍显示 localhost 横幅未告警;init 写文件后 load_config 未 guard(模板恒有效不可触发);test 双读 capsys;demo ctx 省略 snapshot/write_max_bytes(DENY 早于执行,无害)。
- **人工干预**:控制器判定 C1 为真实治理回退(非误报),要求以「围栏锚定 ctx.workspace_root」的架构正确方案(同时修 run+serve)而非仅 CLI 层对齐 config;修复后独立复现确认 secret 不泄漏;折叠 I1/I2 凭据权限修复入同一修复轮。

### Milestone 6 · 最终整支评审(opus)+ I-1/I-2 硬化 — ✅ APPROVED (merge OK)
- **范围**:14 commits,+3192 行(service/interface 层)。全量 231→233。ruff:M6 新增/触碰的文件 0 error(仅 pre-existing 非 M6 文件有 E401/E701 风格债)。
- **SPEC 合规复核(全 PASS)**:§12 自实现主循环无 Agent SDK(grep langchain/autogen/crewai/… 皆无;assembly 直接装配 HarnessCore);§A.4C 离线可测(tests 无 requests/urllib/socket/httpx;serve 测试 monkeypatch uvicorn.run;openai 无 key 在 build_llm 提前 NoKeyError);§13 八端点齐全且命名精确、/credentials/status 仅 {configured,masked}、WebUI 必做集齐(启动+事件流+审批+diff+最终态+审计/verify);C1 围栏修复两处调用点均 ctx.workspace_root 且 run/serve 双路径生效;changed_files 加法式入 TOOL_EXECUTED payload,经 redact+SHA256,verify_chain 确定性不破;凭据 os.open(0o600) 创建期即受限 + makedirs(0o700),getpass 不回显。
- **0 Critical**。集成检查全绿:harness_factory 签名两处调用点一致;跨线程 sqlite 各开连接不共享;WebUI 字段与仓储行形状全对齐;diff 端到端非死代码;demo 真实拦截 rm -rf / (executed count==0);500 handler 不泄漏。
- **I-1(Important,已修 553873d)**:open_db 无 PRAGMA busy_timeout → async 模式后台线程写 audit 与主线程 decide() UPDATE approval 撞写,WAL 单写者下 SQLITE_BUSY 立即抛错 → 审批决定被静默丢弃(行留 PENDING 直到 resolver fail-close,最坏挂 1h)。修:busy_timeout=5000,第二写者等亚毫秒锁而非报错。serve/审批路径正确性修复。
- **I-2(Important,已修 46874b6)**:async pause/resume 从未经 API 层测试(所有 API 测试 sync=True)——正是掩盖 I-1 的集成缺口。补:make_async_api_client(sync=False)+ 两条 HTTP 端到端测试(approve → COMPLETED + 行 APPROVED + chain_valid;reject → 副作用断言 secret.txt 永不落盘 + 行 REJECTED),_poll_http 5s 硬上限防挂。RED 揭示真实行为事实:reject 的写被拒但循环仍可 finish(治理拒的是动作非整轮),故 reject 断言改用确定性副作用。
- **人工干预**:控制器将 I-1/I-2 从"fast-follow 建议"升级为合并前必修(理由:两者都落在本里程碑主推的 serve async 审批路径,且 AegisCode 以审批正确性为卖点);I-1 一行内核修复由控制器直接落地并加 doc 注释,I-2 派 subagent 补 API 层回归测试(同时守护 I-1)。
- **Minor(未阻塞,记录留待清理)**:test_app_service 若干 vacuous 断言(state in 全集 / step_count>=0;机制实为别处严格断言覆盖);redact 未传 workspace_root(绝对路径相对化分支未启用,当前工具皆相对路径无泄漏);test_run_openai 双调 capsys.readouterr()。

---

## 2026-07-14 · Milestone 7(分发与演示)— 新 worktree
**Worktree**:`.claude/worktrees/m7-distribution`,分支同名(base = main @ 7d42001,M0-M6 已并入)。基线 make test = 233。链:T30 Dockerfile → T31 四机制演示 → T32 CI。实现/评审 sonnet。

### Task 30 · Dockerfile + keyring 运行时降级 — ✅ 完成 (1876545, +342fa8e)
- **技能**:subagent-driven-development;实现/评审 sonnet。
- **TDD**:RED = Dockerfile/.dockerignore 不存在,4 测试 FileNotFoundError 全红;GREEN = 实现后 4/4 绿,237 total。
- **产物**:`Dockerfile`(python:3.12-slim,`COPY pyproject.toml + aegiscode/`,`pip install --no-cache-dir -e .`,`EXPOSE 8000`,exec-form `CMD ["aegiscode","serve","--host","0.0.0.0","--port","8000"]`)+ `.dockerignore`(排除 .git/.venv/tests/docs/.env/.env.*/*.pem/*.key/*.db/*.sqlite*/__pycache__/.superpowers/.claude)+ `tests/test_docker_build.py`(4 文本级测试,不需 docker daemon)。
- **安全(SPEC §19 / 决策 #19)**:key 绝不进镜像层(无 `ENV *_KEY`、无 `COPY .env`),运行时 `-e` 注入;workspace `-v host:/workspace` 挂载;容器内 keyring 不可用自动回退 env(T24 `get_key` try/except 已处理)。
- **两阶段评审**:Stage1 SPEC 合规 ✅(key 不烤入、serve 0.0.0.0:8000、editable install 依赖齐全、webui 静态资源随 `COPY aegiscode` 进镜像且 editable 安装直读源码树)。Stage2 质量 — **1 Important(test theater)**:`assert "aegiscode serve" in df` 仅靠头部注释满足(exec-form CMD 把 token 拆成 JSON 数组元素,连续子串不在 CMD 行),删掉整个 CMD 行测试仍绿 → 守卫核心运行时不变量却验的是注释。
- **人工干预(控制器亲自修)**:强化测试断言 exec-form CMD 各 token(`"aegiscode"`/`"serve"`/`"--host"`/`"0.0.0.0"`/`"--port"`/`"8000"`,删/乱序/shell-form 即失败);修 `ENV not in df or API_KEY not in df` 的重言式断言;强化 .dockerignore 测试断言 `*.pem`/`*.key`/`*.db`——**该强化测试立刻抓出真实缺陷**:提交的 .dockerignore 实际不含 `*.pem`/`*.key`(子智能体报告声称已加但提交文件不符,与 M6 的报告-实际漂移同源),已补齐。呼应教训6(守卫必须打在最脆弱的真实路径,不能靠注释/报告自我掩盖)。

### Task 31 · 四个机制演示(§16.4,MockLLM 驱动零网络)— ✅ 完成 (dc8c313, +091440c, +78d4d9f)
- **技能**:subagent-driven-development;实现 sonnet,两阶段评审 sonnet,修复 sonnet。
- **TDD**:RED = `from demos import ...` ModuleNotFoundError;GREEN = 4 demo 测试绿,242 total;audit 修复后 demo1/3 强化断言 RED(KeyError audit_has_deny)→GREEN;entry-point 回归测试 +1 → 243 total。ruff 干净,零网络全 MockLLM。
- **产物**:`demos/demo1_dangerous_denied.py`(rm -rf → DENY)、`demo2_feedback_loop.py`(错误实现→run_tests 失败→修正→通过→finish,最终验证器复跑绿)、`demo3_symlink_escape.py`(evil→/etc/passwd 软链 → PATH_FENCE DENY 无泄漏)、`demo4_superseded.py`(指纹变→SupersededError,相同仍验证通过)。`tests/demos/test_demos.py`。CLI `_cmd_demo` 跑全四个。Dockerfile `COPY demos ./demos`(演示随镜像发布,`aegiscode demo` 可跑)。
- **自包含设计**:各 demo 内联最小装配,不 import tests/helpers → 不受 .dockerignore 排除 tests/ 影响。demo② 用真实子进程(RunTestsTool subprocess)跑 `python check.py`,check 用 exec 原始字节(无 import 缓存)→ 消除 .pyc Heisenbug(评审 42 次确定性运行 0 失败验证)。
- **两阶段评审**:Stage1 SPEC + Stage2 anti-theater。0 Critical;评审用 3 个 falsification probe(ProbeA/B/C)独立证明每条断言机制断则测试失败(demo② COMPLETED 由 final_verifier 复跑赢得非 MockLLM 声称,ProbeC 强制写错→LLM_ERROR 非 COMPLETED)。**2 Important**:demo①/③ 缺 §16.4 强制的 audit GOVERNANCE_DECISION=DENY+rule_id 断言、demo① 缺 POLICY_DENIED feedback 断言。
- **修复(091440c)**:demo①/③ 改为驱动真实 HarnessCore + AuditLog(仿 demo② 模板),经真实 AuditEventRepository 读回事件断言 audit_has_deny/deny_rule_id/feedback_is_policy_denied/no_tool_executed。limits max_steps=1 使第 2 轮 MAX_STEPS 终止,确定性无 LLM_ERROR。真实 harness 完整发出 §16.4 所需事件,无 SPEC 缺口。
- **人工干预(重大)**:子智能体越界改 cli.py 被判定为**正当**——挖出 T29 遗留真实 bug:console script `aegiscode = aegiscode.cli:main` 无参调用 `main()`,但 `def main(argv)` 无默认值 → 所有 `aegiscode ...`(含 Docker `CMD ["aegiscode","serve"]`)启动即 TypeError 崩溃;T29 测试全部显式传 argv 故从未触及真实入口,T30 Dockerfile 评审假设"服务会启动"未跑 console script。控制器确认修复(argv=None→sys.argv[1:])并补零参入口回归测试(78d4d9f),防 docker run 再次静默崩溃。
- **安全/确定性**:全部 MockLLM 零网络;demo③ 反 vacuous 守卫(断言软链 realpath 确实指向 /etc/passwd + 无 root: 泄漏)。

### Task 32 · CI 流水线(unit-test + 密钥扫描 + docker build)— ✅ 完成 (3698399, +966e95d)
- **技能**:subagent-driven-development;实现 sonnet,两阶段评审 sonnet。
- **TDD**:RED = CI 文件 + scripts/ci_secret_scan.py 不存在,6 测试全红;GREEN = 实现后 6/6 绿,249 total;评审 fix 后 8 测试、251 total、ruff 干净。
- **产物**:
  - `.gitlab-ci.yml`(签字 PLAN 指定):stages=[test, security, build];`unit-test`(job 名精确匹配决策 #23)→ `pip install -e ".[dev]"` + `make test`;`secret-scan` → `python scripts/ci_secret_scan.py`(权威闸)+ gitleaks 兜底(`|| echo` 守护,缺二进制不掩盖主判定);`docker-build` → `docker build`。
  - `.github/workflows/ci.yml`(**增值镜像**,非 PLAN 偏离):因 repo 托管于 GitHub,GitLab CI 不会执行;镜像三 job 同构 + gitleaks-action 兜底(continue-on-error),`on: [push, pull_request]` 真正在本 repo 跑起来。PR 描述注明。
  - `scripts/ci_secret_scan.py`:自写确定性闸,复用 T25 `scan_paths`(与脱敏共享同一批正则),仅扫发行面(`aegiscode/`+`demos/`,60 文件),排除 `tests/`(故意假密钥 fixture,且 `.dockerignore` 排除 tests/docs = 不入镜像)。行钉 `ALLOWLIST`=[(assembly.py, 43)](`key = credential_store.get_key()` 的 16 字符标识符 `credential_store` 命中 `(?i)KEY=<16+>`,非真密钥);其余任何位置的同串仍失败(fail-safe)。可 import,`main(argv=None)->int`。
- **安全 / anti-theater**:评审独立跑 plant→scan→delete 证伪:干净→exit0;植入 `aegiscode/_probe_leak.py` 带真 `sk-<40>`→exit1 且点名文件;删除→exit0,无残留。闸真会在发行面拦真密钥。
- **两阶段评审**:Stage1 SPEC ✅(unit-test/make test/secret-scan/docker-build 齐全、stages 正确、GitHub 镜像会触发);Stage2 质量 — 0 Critical。**1 Important**:`test_scan_gate_is_not_vacuous` 只测底层正则,未测闸真实路径(shipped 遍历 + allowlist + 退出码)→ 提交的测试自身不承载 anti-theater 证明。Minor:allowlist 行钉(非宽泛,已验证仅抑制那一行)、tests/ 排除面 = 非发行面(与 .dockerignore 一致)、PyYAML `on:` 解析为布尔键(不影响 Actions 执行与测试)。
- **控制器修复(966e95d)**:强化测试——monkeypatch `REPO_ROOT` 到 temp 树,植入带真密钥的 `aegiscode/leak.py`,断言 `main([]) == 1` 走**完整**遍历+allowlist+退出码路径;补 allowlist 机制测试(仅钉住行被抑制,同串在别处仍失败)。杀掉 regex-only 剧场。251 total 绿。
- **人工干预**:①识别 PLAN 天真快照 `scan_paths(glob('**/*.py'))` 会因 tests/ 故意 fixture 假阳(实测发行面外 54 命中)→ 设计上把闸 scope 到发行面 + 行钉 allowlist,而非削弱 T25 扫描器(其激进正则是脱敏共享资产,测试已钉);②补 GitHub Actions 镜像使 CI 在 GitHub repo 真跑;③强化 anti-theater 测试。

---

## 2026-07-14 · 项目级最终评审 + 收尾修复(Milestone 8 · Hardening）— 新 worktree
**Worktree**:`.claude/worktrees/m8-hardening`,分支同名(base = main @ 0540dba,M0-M7 32 task 全并入)。基线 make test = 251。技能:`requesting-code-review`(项目级,非单 task)+ subagent-driven-development + 严格 TDD。

### 项目级最终评审(§一）— 4 个并行只读 subagent 分片覆盖检查清单
控制器判定:单个 reviewer 覆盖 32-task/251-test 全库过浅,故派 **4 个并行只读评审 subagent**,各领一片 §一 清单,全部 read-only(不动工作树/index/HEAD):
- **片1 主循环 + MockLLM + 停机**:确认主循环 `while True` 由 AegisCode 自写(harness.py:60),无 Agent SDK 依赖;MockLLM FIFO 纯离线确定性;停机四路(invalid/consecutive/no-progress/max-steps)优先级正确无 off-by-one;COMPLETED 靠 final_verifier 复跑客观验证非 LLM 声称。**发现 Important**:循环无 wall-clock 超时 + `urlopen` 无 `timeout=` → 真实 provider 可无限挂起(§一明列"超时"为必需停机条件)。
- **片2 凭据泄漏全面**:确认 redact-before-hash 顺序正确(chain.py:17→23→27);适配器仅把 key 放出站 header 不 log;500 handler 泛化;CLI/status 全掩码;文件后端 0600/0700;镜像不烤 key;git 历史干净。**发现 Important**:redactor+scanner 漏 `sk-proj-`/`sk-svcacct-`(正则无 `-_`)与带引号赋值 → 审计脱敏与 CI 闸盲区;Dockerfile 绑 0.0.0.0 与"localhost-only"文档矛盾。
- **片3 治理绕过(甲命令 / 乙路径 / 审批绑定)**:确认路径围栏对 file tools robust(realpath+commonpath+resolved-sensitive);REQUIRE_APPROVAL 零执行;DENY 执行前中止;matcher 异常 fail-closed。**发现 3 Critical + 2 Important**(下详),控制器逐条独立复现(非只信 subagent)。
- **片4 反馈 / 记忆 / 状态一致性 / 确定性**:确认反馈回灌真实到达下一轮 LLM(test_demo2 断言);COMPLETED 客观;WebUI XSS 安全(textContent);状态单一 sqlite 源。**发现 Important**:记忆子系统建好且单测通过但 `harness._build` 传 `memories=[]`(TODO)未接入主循环;`POST /tasks` 的 workspace 是调用方任意绝对路径。

### Critical(治理绕过,控制器独立复现于 shipped 默认)— 全部已修
- **C1(已修 2c92fa3)**:`python3` 绕过命令规则。allowlist 含 `python3` 但规则仅 `argv0=="python"`,`command_rules` 精确匹配 → `python3 -m http.server` 实测 ALLOW,可跑任意解释器(RCE)。修:`_norm_argv0` 把 `python3`/`python3.12` 折叠为 `python` 仅用于规则匹配(执行的真实 argv0 不变)。
- **C2(已修 2c92fa3)**:紧贴式短选项绕过 `-c` DENY。`shlex.split("python -c'import os'")→['python','-cimport os']`,token `-c` 不作独立元素 → 规则 `-c in args` 不命中 → ALLOW。修:`_arg_matches` 让短选项规则 token 命中独立 `-c` 或紧贴 `-cFOO`(`arg.startswith(tok)`,`--long` 不误入)。
- **C3(已修 57a6c16)**:`run_command` 无路径围栏。`_FILE_TOOLS` 不含 run_command → `cat /etc/passwd`/`cat .env` 实测 ALLOW,绕过敏感文件围栏。修:(a)schema 默认 allowlist 移除 `cat`/`ls`(通用读取器能吃任意路径);(b)dispatcher 新增 `run_command` 路径围栏(`_is_path_like`+`_fence_command`,复用 lex_command+check_path,dispatch/execute_approved 两处),路径型 token 逃逸/敏感即 DENY 不执行。

### Important — 全部已修
- **I1(已修 2c92fa3)**:`git reset --h` 缩写绕过 `--hard` DENY(git 接受无歧义缩写)。修:`_arg_matches` 长选项规则 token 命中其 `>2` 字符前缀(`--h`/`--ha`)与 `--hard=value` 形式;`--soft` 不误命中 `--hard`。
- **I2(已修 2c92fa3)**:`judge_command` 首个匹配即返回,DENY 不具支配性——用户改 YAML 把 ALLOW 排在 DENY 前可静默降级。修:扫描所有命中规则,按严重度阶梯 `DENY>REQUIRE_APPROVAL>ALLOW_WITH_AUDIT>ALLOW` 取最严者。
- **审批指纹绑定接入主循环(已修 a952e1f,Demo 3 依赖)**:`validate_resume`/`fingerprint`/SUPERSEDED 原本仅单测覆盖、未接主循环——harness 把同一 action 对象传 resolver 与 execute_approved,绑定靠对象同一性"碰巧安全"。修:harness 在 REQUIRE_APPROVAL 处捕获 `approved_fp=fingerprint(action)`,`execute_approved(action,ctx,approved_fp=)` 内 `validate_resume` 校验,改动过的动作触发 SupersededError → 返回 denied ToolResult(`artifacts.superseded=True`)+ 审计 APPROVAL_DECIDED/SUPERSEDED + POLICY_DENIED 反馈 + continue 重新判定,绝不执行。控制器独立复现:相同动作执行、改参动作 denied+superseded+不执行。
- **循环 wall-clock 超时 + urlopen timeout(已修 4eeaeb1)**:`Limits.wall_clock_timeout_sec=300`;`decide_termination(c,limits,elapsed_sec=)` 最先检查超时(硬外界界,优先于所有计数器),harness `time.monotonic()` 注入 elapsed(纯函数确定性,key 缺省则跳过=向后兼容);openai_adapter `HTTP_TIMEOUT_SEC=60` 传 `urlopen(timeout=)`,anthropic 复用 `_real_post` 一并覆盖。
- **凭据脱敏正则补全(已修 21a0ee1)**:redactor `OPENAI_KEY=sk-[A-Za-z0-9_-]{20,}`(含 `_-` 覆盖 proj/svcacct,并归并 legacy/ant);`GENERIC_ASSIGNMENT` 加可选引号 `['\"]?` 捕获 `KEY="..."`;`KEY_PATTERNS` 单一真源,scanner 从 redactor import 防漂移。控制器独立验证:proj/svcacct/legacy/ant/带引号全脱敏,benign 不误报,CI 闸仍 0 findings。
- **POST /tasks workspace 路径围栏(已修 594e32e)**:`Workspace.allowed_base`(None=der 自 root);`create_task` 插行前 `_validate_workspace`(realpath+commonpath,symlink 安全、兄弟前缀安全),越界 → `WorkspaceNotAllowedError`→ API 400 且不建 task;CLI 受信操作者显式 `--workspace` 即 allowed_base。控制器验证:根/etc/兄弟前缀/相对/软链全 REJECT,base+子目录 ACCEPT。
- **pyproject starlette 可移植性(已修 b996d7b)**:`filterwarnings` 第 19 行 `ignore::starlette.exceptions.StarletteDeprecationWarning` 是**死配置**(该类是 UserWarning 非 DeprecationWarning 子类,第 18 行 `error::DeprecationWarning` 从不升级它),唯一作用是启动 eager import→在缺该符号的旧 starlette(0.5x)崩 pytest 收集。删之。控制器验证:基线崩溃的 conda py3.13/starlette 0.52 env 现能收集全 283 test。
- **记忆检索接入主循环(已修 1394194)**:`harness._build` 的 `memories=[]` TODO 替换为 `_retrieve_memories()`——`HarnessCore(memory_store=,project_id=)`,retrieve top-k 后经 `is_governance_usable` 过滤(source=agent 记忆"仅提示、永不作治理依据"→ 排除),assembly 构 `MemoryStore(conn)` + `project_id=_workspace_hash(workspace)` 注入。控制器端到端验证:confirmed 记忆到达 LLM 上下文,agent 猜测被过滤。ci_secret_scan allowlist 行钉 43→44(import 位移 `key=credential_store.get_key()`,已核对 line 44 确为该行)。

### 评审方法论与人工干预
- **控制器逐条独立复现**:C1/C2/C3/I1 均以 `/tmp/verify_gov.py` 打真实 `Governance()` shipped 默认复现绕过(非只信 subagent),修后同脚本确认闭合 + 非回归(`--soft` 不误 DENY、`pip install` 仍 REQUIRE_APPROVAL、`python3 script.py` 仍 ALLOW)。
- **每次修复重跑**:定向红队测试 → 模块测试 → 全量 → 相关机制(治理复现脚本 / CI 闸 / 记忆端到端)。全量 251→264→276→283→303→311→315,逐步递增无回归。
- **决策关口(AskUserQuestion)**:治理绕过修复深度=彻底加固;超时+脱敏正则=都修;记忆接入=先核对 PLAN/SPEC 再定(结论:SPEC §524/§537 M10 验收为单测口径已满足,但 T23 显式依赖 T21 且 §一 要求"记忆闭环",`build_context` 本已接主循环仅 `memories=[]` 硬编码 → 接入,低风险~10 行);WebUI 公网部署=先修 workspace 围栏、部署待定。
- **并行 subagent 同 worktree**:片19(脱敏)片20(workspace)触及 disjoint 文件并行跑,控制器分两次提交(21a0ee1 / 594e32e)分离关注点;C1/C2/I1/I2 因同处 judge_command 作为一个 TDD 单元(2c92fa3)避免串行抖动同函数。

### 收尾交付(§三~§十)

#### make demo — 三机制确定性演示入口(已提交 355efb1)
- **背景**:收尾前不存在 `make demo`,仅 `aegiscode demo`(CLI,4 个 §16.4 演示,dict 输出)。§三 硬性要求恰好 3 项、`[Demo N/3]` 分块 + 逐行 `PASS:` + 聚合退出码。
- **产物**:`demos/run_demos.py`(编排器,`DemoSpec(name,index,title,run,checks)` + `_DEMO_BY_NAME` + `main(argv)` + `--only`)、`demos/demo3_approval_binding.py`(新,完整审批生命周期)、`tests/demos/test_run_demos.py`(4 测)、`tests/demos/test_demo3_approval_binding.py`(1 测)、`Makefile`(`demo`/`demo-guardrail`/`demo-feedback`/`demo-approval`,`PY ?= python`)。
- **Demo 3 深度**:demo4_superseded 仅 fingerprint 级 `validate_resume`,不足 §3.1 要求的完整活循环生命周期。新 demo3_approval_binding 驱动真实 HarnessCore + 变异 approval_resolver(round1 原样批准→执行;round2 批准后变异 arguments→ 指纹分歧→SUPERSEDED→不执行),经真实 AuditEventRepository 读回证明六项保证(暂停时 exec=0 / 规范化快照+指纹存储 / 原动作执行 / 变异 SUPERSEDED / 变异不执行 / APPROVED→SUPERSEDED 审计流)。依赖本轮 a952e1f 审批绑定接线。
- **TDD**:orchestrator 测先红(ImportError)→ 实现 → 4 绿;demo3 测先红(ModuleNotFound)→ 实现 → 1 绿。`make demo` 退出 0(3 passed);强制某 demo 契约失败→退出非 0(反"吞错返回成功")。全量 316→320。
- **注**:demo① `deny_rule_id` 由 `CMD_ALLOWLIST`→`CMD_PATH_FENCE`(C3 修复的**后果**:`rm -rf /` 现先命中路径围栏,`/` 逃逸 workspace)。仍 DENY/executed=0/已审计,demo① 测断言 truthy rule_id 非特定值故不破。两个 `demo3_*` 文件不同入口共存(`make demo`→approval,`aegiscode demo`→symlink)。

#### CI 加入 make demo(§七,已提交 8a02d9f)
- `.gitlab-ci.yml` 与 `.github/workflows/ci.yml` 的 `unit-test` job 均在 `make test` 后追加 `make demo`(MockLLM,无 key,无 `|| true` 守护)。任一演示失败即 job 失败。两文件 YAML 解析校验通过,`unit-test` job 名精确保留。

#### 凭据安全审计(§六,已完成)— PASS,0 Critical / 0 Important
- subagent 只读审计 12 面(源码/配置/git 历史/.env/fixture/日志/审计链/WebUI/API/Dockerfile/构建 arg+镜像 env/错误栈)。
- **全生命周期经验验证**:未配置(`configured:False`)→ getpass 安全录入 + 文件 0600 → status 仅掩码(first3…last4,<8→`***`,明文不现)→ 更新覆盖 → clear(`configured:False`)→ 清除后 `build_llm` 抛 `NoKeyError` 不触网。
- **redact-before-hash 确认**:`chain.py:17` 在 SHA256 与 DB insert **之前** redact。
- **git 历史**:141 commit 仅规范假密钥(`AKIAIOSFODNN7EXAMPLE` 为 AWS 官方文档示例,其余显式占位),全在 tests/ 或 docs/PLAN.md 代码片段。`ci_secret_scan` 发行面 0 findings。
- **Minor(记录未阻塞)**:scanner 有意限于 `sk-`/`AKIA`/`KEY=` 形态,不含 `sk-` 前缀的第三方 key 会漏——对本应用威胁模型(自身 OpenAI/Anthropic key)可接受,非通用密钥探测器。

#### 干净环境验证(§五,已完成)— 全绿 + 挖出 1 真实 bug
- **命令与退出码**:`make test` → 321 passed;`make demo` → exit 0(3 passed);`docker build -t aegiscode:m8 .` → 成功(clean `pip install` 解析到 starlette-1.3.1,证可移植性修复在全新环境成立);`docker run` → 容器 running,退出 status 0 无残留进程。
- **挖出真实 bug(已修 1fc6ea4)**:§五 clean-env 测试暴露 `_load_config` 无配置文件时**直接返回 `AegisConfig()`,绕过 `load_config` → `AEGIS_LLM_PROVIDER` 环境覆盖被静默忽略**。容器内无 aegis.yaml,故 `serve` 恒用 `provider=openai`,`-e AEGIS_LLM_PROVIDER=mock` 无效 → MockLLM 模式无法起服务(破 §五/§八)。TDD 修:loader 抽出 `_apply_env_overrides` 单一真源 + `load_defaults(env)`,无文件路径也应用覆盖;红(openai≠mock)→ 绿。321 passed。
- **容器内经验验证(修复后重建镜像)**:`-e AEGIS_LLM_PROVIDER=mock` 无 key 起服务成功;`GET /`=200 + 标题 + app.js/style.css 加载;`/credentials/status`=`{"configured":false,"masked":null}`(无明文);workspace 围栏在容器内生效(`POST /tasks` 越界 `/tmp/acc`→400,in-base→200);镜像 `GPG_KEY` 与 stock `python:3.12-slim` 逐字节相同(Python 发行签名公钥,非本项目密钥);容器 clean exit(0)无 stray 进程。
- **`GET /tasks` 405**:设计如此(无 collection-GET 路由,任务经 `GET /tasks/{id}` 读),非缺陷。

#### 最终整分支评审(§二,opus)— 0 Critical / 1 Important(已修)
- opus reviewer 读全量 `main..HEAD`(16 commit,+2299/-47),跑 `pytest`(321)+ 两个 demo 入口,并构造对抗探针(22 条命令、fence 越界/敏感)。**0 Critical**:命令治理、审批绑定、双路径围栏、workspace 围栏、超时全部扛住,每个失败模式都 fail-closed。
- **1 Important(已修 11f0995)**:`run_command` 路径围栏**误拒**参数中仅"包含"敏感词的合法命令——`git commit -m added-credentials-helper`、`git checkout credentials-fix`、`git branch feature/credentials` 全被 `CMD_PATH_FENCE` 硬拒,把 `git commit` 从应有的 REQUIRE_APPROVAL 静默降级。fail-closed(过度拦截非漏洞),但破坏 agent 常用的受治理路径(commit message/branch 名由模型生成、含 "credentials" 很常见)。
- **控制器独立复现 + TDD 修复**:分离 fence 混淆的两种威胁——**逃逸**(路径解析到 workspace 外,对**任何**命令都是威胁→恒拒,`git apply /etc/passwd`/`python ../x`/`rm -rf /` 仍拒);**敏感名**(workspace 内、basename 命中 `.env`/`*.pem` 等,仅当命令**把它当文件消费**——python/pytest/ruff/mypy——才是读/执行威胁;git/pip 的裸敏感词 token 是 ref/message/package 非文件访问,不 fence,交策略引擎判定,`python .env`/`key.pem` 仍拒)。另停止 fence argv0(allowlist own 它)。4 条非回归测试,全量 321→325,make demo 3 passed。
- **Minor(评审记录,未阻塞)**:demo1 docstring 陈旧(`rm -rf /` 现经 `CMD_PATH_FENCE` 拒非 allowlist,已顺手修);两套 demo 入口共存(`make demo` 评分集 / `aegiscode demo` SPEC 集,README §10 已注明,可合并后整合);`ci_secret_scan` 行钉 43→44 已核对无误。

#### CI 补充:GitHub Actions 硬化(2026-07-15 14:43 CST,分支 `chore/github-actions`)
- **任务**:补充/硬化 GitHub Actions CI(交付增强,非原始 PLAN 遗漏——见 PLAN §「收尾追加任务」)。
- **修改原因**:`.github/workflows/ci.yml` 此前已存在(commit 3698399/8a02d9f,`on: [push, pull_request]`,三 job),但缺 §三 手动触发、§四 最小权限、§五 并发控制、§八 缓存、§九 step 命名。本次在**不改测试真相来源**(仍复用 `make test`/`make demo`,不复制测试逻辑)的前提下补齐。
- **参考的现有 GitLab CI**:`.gitlab-ci.yml`(stages test/security/build;`unit-test`→`make test`+`make demo`;`secret-scan`→`ci_secret_scan.py`+gitleaks 兜底;`docker-build`→`docker build`)。GitHub Actions 保持同构,job 名 `unit-test` 精确保留(决策 #23)。
- **新增/修改 workflow 文件**:`.github/workflows/ci.yml`(单文件硬化,未新建重复 workflow)。
- **触发条件**:`push: branches:[main]` + `pull_request:`(任意分支的 PR) + `workflow_dispatch:`(手动)。选此以精确覆盖「推 main / 对 main 的 PR / 手动」,feature 分支经其 PR 触发避免 push+PR 同 commit 双跑;不引入路径过滤(遵 §三简单可靠)。
- **权限配置**:顶层 `permissions: contents: read`(最小权限);未申请任何写权限,GITHUB_TOKEN 保持只读。
- **并发**:`concurrency.group=${{ github.workflow }}-${{ github.ref }}`,`cancel-in-progress: true`(同 ref 新推送取消旧运行;不同分支互不影响)。
- **Job 结构**:①`unit-test`(setup-python 3.12 + pip 缓存 → `pip install -e ".[dev]"` → `make test` → `make demo`;test/demo 同 job——环境相同且 demo 秒级,拆分只重复装依赖无收益,遵 §七);②`secret-scan`(`ci_secret_scan.py` 权威闸 + gitleaks-action@v2 `continue-on-error` 兜底);③`docker-build`(`docker build -t aegiscode:ci .`,仅构建不推送)。
- **运行时版本**:Python 3.12——与 pyproject(`>=3.12`)/Dockerfile(`python:3.12-slim`)/GitLab CI 一致。
- **统一命令**:`make test`、`make demo`、`docker build`(测试真相来源=Makefile,两 CI 共用)。
- **本地验证结果**:`make test` → **325 passed**(1 warning,starlette/httpx 弃用,非本项目);`make demo` → **3 passed / 0 failed(exit 0)**;`tests/test_ci_config.py` → **8 passed**;两 CI YAML 均 `yaml.safe_load` 解析通过,GH 三 job/权限/并发/触发核对无误,GitLab `unit-test` 仍在且跑 `make test`。
- **Docker 构建结果**:`docker build -t aegiscode:ci .` → **成功**(镜像 `aegiscode:ci`)。
- **凭据安全检查**:workflow 未写入/硬编码任何 API Key / token / `.env` / registry 密码;`make test`/`make demo` 全程 MockLLM、零网络、无 Secret;`git diff` 未引入真实凭据(徽章/ACCEPTANCE 仅含公开 repo 地址 `HELLOI9/AegisCode`)。
- **actionlint/yamllint**:环境**未安装**,不擅自全局安装不受控软件;以 Python `yaml.safe_load` + `tests/test_ci_config.py` 静态校验替代,**GitHub 远端运行为最终验证**。
- **人工审阅与修改**:保留现有三 job 与测试逻辑,仅补硬化项;docker tag 由 `aegiscode` 改为 `aegiscode:ci`(与本任务 §七 一致,不影响语义)。
- **GitHub 远端运行**:**✅ 已完成并成功**。推送分支 `chore/github-actions` → PR [#10](https://github.com/HELLOI9/AegisCode/pull/10) → Actions [run 29395362746](https://github.com/HELLOI9/AegisCode/actions/runs/29395362746)(event=pull_request,commit `bd98d9c`)三 job 全绿:unit-test(23s)/secret-scan(19s)/docker-build(20s),conclusion=**success**。
- **远端观察与后续修正**:①push 事件未在 feature 分支双触发(触发设计 `push[main]` 生效),仅 PR 触发一次;②gitleaks 兜底步骤报 `GITHUB_TOKEN is now required to scan pull requests`——因 `continue-on-error: true` **未使 job 失败**(自写 `ci_secret_scan.py` 为权威闸,已通过),但兜底实为 no-op 并在绿色运行上留红 X 注解。修正:向该 step 注入自动提供的只读 `GITHUB_TOKEN`(`env.GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}`),使兜底真正生效,**不扩大权限**(仍 `contents: read`,不发评论),符合 §四。③Node20 弃用为 GitHub runner 侧信息注解,与本项目无关。
