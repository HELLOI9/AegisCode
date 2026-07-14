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

### Task 11-17 · 治理其余任务 — ✅ 全部完成
(逐任务细节见 progress.md 账本;此处记里程碑与最终评审)
- T11 路径围栏(乙) fd91949 +1cde65e(sibling-prefix)+b48f4a9(符号链接指向敏感文件绕过修复,M2 最终评审发现)
- T12 受治理分发器 c62f0e0 +e752c54(no-exec spy 断言);含 T10 carried 的 matcher 异常 guard→INTERNAL_ERROR
- T13 命令词法(甲1-2) 9f1b33c +40bc08c(CRITICAL:glob 注入缺失 + newline + _META 排序修复)
- T14 命令规则(甲3-4) 85a1905 +839ceac(多token ALL-match 边界);demo① rm -rf→DENY / pip install→APPROVAL 实测通过
- T15 审批状态机 cedc259 +85f9ad3;fingerprint+validate_resume 背书 demo④ SUPERSEDED
- T16 run_command 执行器 b64465b;shell=False+argv 确认
- T17 run_tests 传感器+finish 93d1ca7;修 brief bug t_ok.py→test_ok.py;run_tests 固定命令不可被 arguments 劫持

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

### 逐任务(细节见 progress.md 账本)
- T25 secret scanner b39c3ca +f271fd7(修 open() 句柄泄漏)。复用 redactor 的 4 类 key 模式。
- T18 反馈分类+pytest摘要+ProgressTracker c0df597 +422f0f8(修返回注解 + 硬限摘要行数)。8 类失败分类;deque(maxlen=3) 无进展窗口。
- T19 审计 SHA256 哈希链 af405cf +8c36acb(修 utcnow 弃用) +7f1477d(显式 commit 保证持久 + 补 hash篡改/删除 篡改类测试)。GENESIS 0*64,payload 写前脱敏,verify_chain 返回篡改 step。
- T20 记忆存储 738ad8a +ce70499(补跨项目隔离测试)。写前 scan_text 拒绝密钥;source=agent→confirmed=False + is_governance_usable=False;参数化 SQL 无注入。
- T21 上下文构建 932e893 +b633118(修 tier 4/5 顺序 feedback 先于 memories)。确定性 summarize、零 LLM、system 永不丢弃。

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
