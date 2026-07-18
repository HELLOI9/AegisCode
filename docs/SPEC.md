# AegisCode — SPEC（设计规约）

> **AegisCode** — A policy-governed coding agent harness with deterministic feedback loops.
>
> 本文档由 brainstorming 阶段（25 轮设计问答）沉淀而成，过程记录见 [`SPEC_PROCESS.md`](./SPEC_PROCESS.md)。
> 本文档**只整理已确认的设计决策**；仍未解决者一律标记为「未决问题」，不做猜测。
> 本阶段不含实现代码。

---

## 目录

1. 问题陈述
2. 目标用户与项目价值
3. 用户故事（INVEST）
4. 核心使用场景（黄金路径）
5. MVP 范围与非目标
6. 功能规约（按模块）
7. 非功能性需求
8. 系统架构
9. 数据模型
10. 领域与机制设计（§A.5 独立章节）
11. 治理与安全护栏：主要贡献（独立章节）
12. 凭据威胁模型
13. 凭据与分发设计
14. 技术选型与理由
15. 验收标准
16. 确定性机制与 MockLLM 测试策略
17. 风险、限制与未决问题

---

## 1. 问题陈述

当 LLM 能完成大部分编码"思考"时，把一个"只会产生下一步设想"的 LLM 封装成一台**稳定、可靠、可信**的系统，价值落在 harness 这层工程上。现有 Coding Agent（Claude Code、Codex 等）的安全治理多为产品化黑盒或系统提示词约束：使用者无法独立验证"哪些动作会被拒、哪些进审批、为什么"，也无法在移除 LLM 后对这些判定做确定性测试。

AegisCode 要解决的问题：**让开发者敢把本地代码仓库交给一个 Agent 去修改**——通过把安全治理从"系统提示词里的一句嘱托"变成一套**确定性、可单测、可审计的策略引擎**。

**差异化主句（核心定位）：**

> AegisCode 把 Coding Agent 的安全治理从"系统提示词里的一句嘱托"变成一套**确定性、可单测、可审计的策略引擎**：每条拒绝/审批判定都能脱离 LLM 用单元测试验证，每次动作都留下防篡改的审计证据。

**定位取舍：** AegisCode **不以补丁的智能程度竞争**（那取决于底层 LLM，不是本项目的工程），**只以治理的确定性与可验证性竞争**。演示中刻意使用不算聪明的 MockLLM，反而更能凸显"即使 LLM 犯浑，harness 也守得住边界"。

---

## 2. 目标用户与项目价值

**核心目标用户：** 担心 Agent 越权访问（读 `.env`/凭据、逃出工作区）或执行危险命令（`rm -rf`、`git push`、装依赖），但仍希望用 Agent 修改本地代码的开发者。

**次要用户：** 想观察 Agent 每轮内部状态、审批高风险操作、查看审计记录的学习者与 harness 机制研究者。

**核心价值：** 确定性 + 可单测 + 可审计的策略引擎；每次动作留下防篡改审计证据。信任来自可追溯，而非"相信 LLM 会听话"。

**Main Contribution（深度维度）：治理**。两个出口深挖：
- **甲 = 命令词法治理**（shell 出口）；
- **乙 = 路径围栏**（文件出口）。
- 丙（网络/发布/外部副作用）只做粗粒度（默认禁止或一律进审批）。

反馈闭环是**完整但非最深**的第二支柱（Agent 必须能据客观信号自我修正）。

---

## 3. 用户故事（遵循 INVEST）

- **US-1（危险命令拦截）：** 作为担心破坏性操作的开发者，我希望当 Agent 试图执行 `rm -rf`、`sudo`、`git push` 等危险命令时被确定性拦截，以便我的系统不会被误操作破坏。
  - 验收：构造该动作 → 治理返回 DENY；工具执行次数为 0；审计记录拒绝原因。

- **US-2（作用域限制）：** 作为开发者，我希望 Agent 无法读写工作区之外的文件（包括通过 `..`、绝对路径、符号链接逃逸），以便凭据与系统文件不被触碰。
  - 验收：构造逃逸路径 → DENY；未读到/写到工作区外内容。

- **US-3（人工审批）：** 作为开发者，我希望灰色地带操作（如 `pip install`）暂停并等我批准，批准后只执行我看过的那个动作，以便我对高风险动作保有控制权。
  - 验收：REQUIRE_APPROVAL 暂停；批准执行原始快照；拒绝则反馈回灌 Agent 继续。

- **US-4（客观反馈自我修正）：** 作为开发者，我希望 Agent 根据真实测试失败信息修改下一步动作，而不是空转或谎称完成，以便它能真正把任务做对。
  - 验收：测试失败反馈进入下一轮上下文；下一次动作与上次不同；最终由 harness 复跑测试判定成功。

- **US-5（可审计）：** 作为开发者，我希望完整追溯 Agent 每个动作、每次治理判定、每次审批结果，且审计记录防篡改，以便事后核查。
  - 验收：审计事件流可查看；`verify_chain` 校验通过；篡改任一条 → 校验失败。

- **US-6（凭据安全）：** 作为开发者，我希望安全录入/查看/清除 LLM API Key，查看时不回显明文，且 Key 绝不进入源码、Git、日志，以便凭据不泄漏。
  - 验收：`key status` 只显示已配置+掩码；secret scanner 能检出被植入的假 Key。

- **US-7（声明式约束）：** 作为开发者，我希望通过配置文件声明工作区、允许/禁止的命令、需审批的动作，且规则由代码强制执行（非 LLM 自觉），以便约束可被独立验证。
  - 验收：修改配置能改变治理判定（单测）；非法配置启动即报错。

---

## 4. 核心使用场景（黄金路径）

用户选择一个本地 Python 项目并提交一个局部修复任务。AegisCode 的确定性剧本：

1. 用户提交任务；
2. （轮1）Agent `read_file` 读取相关代码 —— 路径围栏校验通过，ALLOW;
3. （轮2）Agent 请求 `run_command: "pip install <lib>"` —— 治理判定 **REQUIRE_APPROVAL**，任务暂停；
4. 用户**拒绝** —— 产生 `APPROVAL_REJECTED` 反馈回灌；
5. （轮3）Agent 改用标准库重写，`write_file` —— 路径围栏校验通过；
6. （轮4）Agent `run_tests` —— 测试**失败**，产生 `TEST_FAILURE` 反馈（截断脱敏）回灌；
7. （轮5）Agent 根据失败信息修正，`write_file`;
8. （轮6）Agent `run_tests` —— 测试**通过**;
9. Agent 请求 `finish` —— harness **独立复跑目标测试 = 全绿**，且无越界、无待审批 → **COMPLETED**。

任何越过工作区、安装依赖、删除文件或执行高风险命令的操作，都会被拒绝或进入人工审批。**完成判定不依赖 LLM 声称，而由 harness 的最终验证器复跑测试决定。**

---

## 5. MVP 范围与非目标

### 5.1 Must（第一版必做）
单用户 / 单任务 / 单个本地仓库 / **锁定 Python + pytest 单栈**；自实现 Agent 主循环 + LLM 抽象层（OpenAI + Anthropic + MockLLM）；结构化动作协议 + 工具注册分发；治理引擎（甲命令词法治理 + 乙路径围栏 + 四档判定 + HITL 审批状态机 + 审计哈希链）；反馈闭环（pytest + 命令退出码 + 文件变更范围检查）；停机与防死循环；SQLite 最小记忆（无向量库）；YAML 声明式配置；极简 WebUI;CLI；凭据 keyring + `.env` 降级；Docker + CI。

### 5.2 Should（延后，不影响核心闭环）
`ruff`（lint）与 `mypy`（typecheck）作为额外反馈传感器；自动回滚（写前快照 + `rollback_task`）；WebUI 实时推送 SSE。

### 5.3 Won't / 非目标（明确写入，不做）
完整替代 Claude Code；多 Agent 编排；并行子 Agent；云端仓库自动修改；远程服务器控制；自动部署生产；自动 `git push`；大规模代码库索引；向量/语义检索；多用户权限系统；企业级沙箱；**多语言支持**;**通用 shell 的完整安全化**;**任务并发**。

---

## 6. 功能规约（按模块）

> 每模块给出：输入 / 行为 / 输出 / 边界条件 / 错误处理。所有"机制"均为确定性代码（见 §10 领域与机制设计、§16 MockLLM 测试策略）。

### M1 · Agent 主循环
- **输入：** 用户任务、工作区路径、配置。
- **行为：** 严格单动作循环——构建上下文 → 调 LLM → 解析 1 个 Action → 治理判定 → （审批暂停） → 工具执行 → 反馈分类回灌 → 落盘 → 停机判定。`run_tests` 兼具工具与反馈传感器身份；`finish` 触发 harness 独立最终验证。
- **输出：** 每轮一条 `steps` 记录 + 审计事件；终止时给出 TerminationReason。
- **边界：** 达 max_steps / 连续失败 M / NO_PROGRESS 阈值 → 停机；审批处暂停并持久化。默认阈值 **max_steps=25 / 连续失败 M=5 / NO_PROGRESS 累计=3**（均可 YAML 覆盖）。
- **停机原因枚举（TerminationReason,9 种）：** `COMPLETED`（finish 且最终验证全绿、无越界、无待审批） / `FINISH_REJECTED`（finish 但验证未过→回灌继续，撞上限转 MAX_STEPS） / `MAX_STEPS` / `CONSECUTIVE_FAILURES` / `NO_PROGRESS` / `INVALID_ACTION_LIMIT`（连续 3 次无效动作） / `LLM_ERROR` / `INTERNAL_ERROR` / `CANCELLED`（用户取消）。
- **每轮判定优先级（从高到低，短路）：** ① 内部异常→INTERNAL_ERROR 停 ② 用户已取消→CANCELLED 停 ③ 动作无效→计数，连续 3 次→INVALID_ACTION_LIMIT 停，否则回灌纠错继续 ④ 治理 DENY→回灌 POLICY_DENIED，计入连续失败，**不停** ⑤ 治理 REQUIRE_APPROVAL→暂停（不算失败）⑥ 工具执行→反馈回灌，failure/error 则连续失败+1、成功清零 ⑦ 动作是 finish→跑最终验证，过→COMPLETED，不过→回灌继续 ⑧ 轮末检查计数类停机（MAX_STEPS/CONSECUTIVE_FAILURES/NO_PROGRESS）。审批被拒 → 继续（APPROVAL_REJECTED 反馈 + 计入连续失败）。
- **错误：** LLM 调用失败退避重试 3 次后 `LLM_ERROR` 停机；harness 内部异常 → `INTERNAL_ERROR`。

### M2 · LLM 抽象层
- **输入：** 消息列表 + 参数。
- **行为：** 统一 `LLMClient` 接口；实现 `OpenAIAdapter`（chat completions，可配 base_url）、`AnthropicAdapter`（messages API）、`MockLLM`（按序响应队列）。协议差异封装在适配器内，主循环不感知厂商。
- **输出：** 文本补全。
- **边界：** MockLLM 零网络、零 Key。
- **错误：** 真实适配器网络/鉴权失败向主循环抛出，由重试逻辑处理。

### M3 · 结构化动作协议
- **输入：** LLM 原始文本。
- **行为：** 稳健 JSON 提取（优先 ```json 围栏，否则取最后一个平衡 JSON 对象）→ Pydantic 校验（类型/必填/tool 在注册表/arguments 匹配工具 schema）。动作模型 `{thought, tool, arguments, expectation?}`，`finish` 为独立工具。
- **输出：** 校验通过的 Action 对象。
- **边界：** 多余散文由 `thought` 字段承接。
- **错误：** 校验失败 → `INVALID_ACTION` 结构化纠错反馈回灌；连续 3 次无效 → `INVALID_ACTION_LIMIT` 停机。未知工具 → INVALID_ACTION；被配置禁用的工具 → 治理 DENY（区分二者）。

### M4 · 工具注册与分发
- **输入：** Action。
- **行为：** 工具接口统一；注册表查找；参数校验；治理判定后执行；错误捕获；结果标准化为 ToolResult。
- **输出：** ToolResult。
- **边界：** 7 个工具：`list_files` / `read_file` / `search_text`（纯 Python 遍历）/ `write_file`（全量覆盖、仅文本、写前快照、大小限制）/ `run_tests` / `run_command` / `finish`。
- **错误：** 工具执行异常 → `TOOL_ERROR`；二进制文件读取 → 结构化"已跳过"而非乱码。

### M5 · 治理引擎（甲 · 命令词法治理）
- **输入：** `run_command` 的命令**字符串**。
- **行为：** 5 层确定性管线——① shlex 词法解析（失败=INVALID_ACTION）② 结构安全层（管道/重定向/串联/命令替换/子 shell/后台/通配注入 → 一律 DENY）③ 允许列表（argv0 不在白名单 → DENY）④ 危险参数级规则 ⑤ 执行层（`shell=False` + argv 数组 + 超时 + 输出上限 + cwd 锁工作区，永不 `shell=True`）。
- **输出：** 治理判定（四档）+ rule_id + reason；或标准化命令结果。
- **边界：** DENY = `rm -rf`/`sudo`/`su`/`chmod`/`chown`/`curl`/`wget`/`git push`/`git reset --hard`/`git clean`/`python -c`/`python -m <inline>`/任意元结构；REQUIRE_APPROVAL = `pip install`/`git commit`/写非白名单目录。
- **错误：** 词法解析失败 → INVALID_ACTION；命令超时 → TIMEOUT。

### M6 · 治理引擎（乙 · 路径围栏）
- **输入：** 文件工具的路径参数。
- **行为：** ① 拒空/非字符串 ② 相对路径拼 workspace_root，绝对路径允许但须 realpath 后在工作区内 ③ realpath 解析（解掉 `..` + 符号链接）④ 归属判定 `is_relative_to(realpath(root))`，否则 DENY ⑤ 敏感文件黑名单 DENY ⑥ 通过则交类别默认档。新建文件对**父目录**做 realpath 归属判定 + 校验文件名非软链。
- **输出：** 治理判定 + rule_id + reason。
- **边界：** 路径穿越 / 绝对路径越界 / 符号链接逃逸 → DENY；敏感文件（`.env`/`.git/`/`*.pem`/`*.key`/`*credentials*`）读写皆 DENY；仅支持 Linux。
- **错误：** 不存在的父目录 → TOOL_ERROR（而非误判越界）。

### M7 · 人工审批状态机（HITL）
- **输入：** 治理判定为 REQUIRE_APPROVAL 的动作。
- **行为：** 任务转 APPROVAL_REQUIRED 暂停，持久化 ApprovalRequest（action_snapshot + fingerprint + rule_id + reason + risk_explanation）；用户裁决后恢复。
- **输出：** APPROVED → 执行原始动作快照；REJECTED → `APPROVAL_REJECTED` 反馈继续。
- **边界：** 动作指纹变 → SUPERSEDED 需重审；"记住批准"限完全相同指纹（本任务内）；恢复只执行原始快照。
- **错误：** 审批无超时（EXPIRED 状态预留但 MVP 不启用）。

### M8 · 审计与哈希链
- **输入：** 主循环各阶段事件。
- **行为：** 每任务 append-only 事件流，event_type 7 类；`hash = SHA256(prev_hash ‖ 规范化本条内容)`；写入前脱敏。
- **输出：** `audit_events` 记录；`verify_chain(task_id) -> bool` 校验完整性。
- **边界：** 只做 SHA256 可检测篡改，不做 HMAC 签名（→未来）。
- **错误：** 链断裂 → verify_chain 返回 False 并指出断点。

### M9 · 反馈闭环
- **输入：** ToolResult / 治理判定 / 异常。
- **行为：** 标准化为统一结构，`detail_for_llm`（截断+脱敏）与 `artifacts`（完整，仅审计/WebUI）分离；失败分类 8 类；精简回灌 + 确定性脱敏 + 重复动作指纹 K=3 判 NO_PROGRESS。
- **输出：** 写入下一轮上下文的结构化反馈。
- **边界：** pytest 只回灌失败名 + 断言行 + traceback 末 20 行。
- **错误：** 只拦完全重复动作，不臆测语义相似。

### M10 · 记忆与上下文
- **输入：** 记忆写请求 / 上下文构建请求。
- **行为：** 三分层（跨会话 Memory / 任务级状态 / 审计）；检索 = type + project_id + 关键词 LIKE + last_used_at + topK（无向量库）；写入过脱敏器；上下文 6 段优先级装配 + 字符数近似 + 超预算确定性摘要化最旧轮（不调 LLM）。
- **输出：** memories 记录 / 组装好的上下文。
- **边界：** Agent 可提议写记忆（source=agent, confirmed=false，仅提示、永不作治理依据）。
- **错误：** 命中密钥/`.env`/凭据模式 → 拒写或擦除。

### M11 · 声明式配置
- **输入：** `aegis.yaml`。
- **行为：** 代码内置默认 + YAML 覆盖 + 少数环境变量覆盖；加载时 Pydantic 校验；规则由配置驱动（改配置改变判定）。
- **输出：** 校验通过的配置对象。
- **边界：** `command_rules` 每条是**扁平结构** `{argv0: str, args_contain: [str], decision}`（argv0 为**单个字符串**，非列表；token 包含匹配；正则→未来）；`write_allowlist_dirs` 内写默认 ALLOW。配置模型 **`extra="forbid"`**：未知字段直接报错；`decision` 与 `default_decisions.*` 的取值须是四档枚举之一，否则报错。**危险命令规则（下方 `command_rules` 那 7 条）是 harness 的代码内置默认（secure-by-default）：即使不加载任何 `aegis.yaml`，治理规则也已生效**——这兑现 §A.4B"机制是代码而非配置内容"，也堵住"省了 config 就静默放行 pip install"的 fail-open。YAML 里若提供 `command_rules`，则**全量替换**该默认（声明式覆盖）；出厂 `aegis.yaml` 只是把这份代码默认显式写出以便查看/覆盖。
- **错误：** 未知字段/类型错/枚举越界 → 启动即报错，不进主循环（`ConfigError`）。环境变量覆盖仅限 `AEGIS_LLM_PROVIDER`、`AEGIS_LLM_MODEL` 两项；`load_config(path, env=None)` 中 `env=None` 时读 `os.environ`。

**`aegis.yaml` 结构（八段；数值项凡标注为示例者见 §17.5 未决问题）：**
```yaml
workspace:
  root: "/workspace"
limits:                          # max_steps/M/NO_PROGRESS/action_retry 为已确认默认;超时/字节数为示例待校准
  max_steps: 25
  max_consecutive_failures: 5
  no_progress_repeat_limit: 3
  action_retry_limit: 3
  command_timeout_sec: 30        # 示例(UQ5)
  output_max_bytes: 65536        # 示例(UQ5)
tools:
  enabled: [list_files, read_file, search_text, write_file, run_tests, run_command, finish]
  write_max_bytes: 1048576       # 示例(UQ5)
feedback:
  test_command: "pytest -q"
  target_tests: "tests/"
governance:
  command_allowlist: [python, python3, pip, pytest, ruff, mypy, git, ls, cat]   # 含 pip(否则 pip install 在允许列表层即被 DENY,走不到审批)
  command_rules:                 # 有序 first-match;每条扁平 {argv0:str, args_contain:[str], decision}
    - {argv0: git, args_contain: ["push"], decision: DENY}
    - {argv0: git, args_contain: ["reset", "--hard"], decision: DENY}
    - {argv0: git, args_contain: ["clean"], decision: DENY}
    - {argv0: git, args_contain: ["commit"], decision: REQUIRE_APPROVAL}
    - {argv0: pip, args_contain: ["install"], decision: REQUIRE_APPROVAL}
    - {argv0: python, args_contain: ["-c"], decision: DENY}
    - {argv0: python, args_contain: ["-m"], decision: DENY}
    # 注:sudo/su/rm/chmod/chown/curl/wget 不在 command_allowlist,由默认档 command:DENY 兜底,
    #     无需(也不能)用列表 argv0 逐条列——argv0 恒为标量字符串。
  sensitive_file_patterns: [".env", ".git/", "*.pem", "*.key", "*credentials*"]
  write_allowlist_dirs: ["src/", "tests/"]
  default_decisions: {readonly: ALLOW, write: REQUIRE_APPROVAL, command: DENY}
memory:
  retrieval_top_k: 8             # 示例
  context_budget_chars: 24000    # 示例(UQ1)
credentials:
  allow_dotenv: false            # fail-safe 默认关闭
llm:
  provider: openai               # openai | anthropic
  model: "gpt-4o"
  base_url: null
```

### M12 · 凭据管理
- **输入：** CLI `key set/status/clear`。
- **行为：** 存储分层 keyring → `.env`(gitignore + chmod600)→ 环境变量；getpass 隐藏录入；`.env` 降级默认关闭（fail-safe）。
- **输出：** status 只返 `configured` + 掩码，永不明文。
- **边界：** 容器内 keyring 不可用自动回退环境变量；secret scanning = 自写可单测扫描器 + CI gitleaks。
- **错误：** 读取失败只报"未配置"，异常不打印 key。

### M13 · WebUI / REST API
- **输入：** HTTP 请求。
- **行为：** 异步执行（POST /tasks 立即返 task_id，后台跑循环，每轮落 SQLite）；实时状态用轮询（GET events?since=N）；8 端点。
- **输出：** JSON 响应 / WebUI 页面。
- **边界：** WebUI 必做=启动+事件流+审批面板+diff+最终状态+审计；前端豁免 Open Design，极简原生。
- **错误：** credentials/status 掩码不回显；重启不自动续跑但可查看 + 可从 APPROVAL_REQUIRED 恢复。

### M14 · 分发与部署
- **输入：** Docker build/run。
- **行为：** 单一 Docker 形态，推公开 registry,key 运行时注入；workspace 用 `-v` 挂载 /workspace。
- **输出：** 可运行容器 + 公网 demo URL。
- **边界：** 云端 demo = 演示沙箱（预置玩具项目 + 最窄允许列表 + MockLLM）；主场景本地自带 key 零鉴权。
- **错误：** key 绝不 COPY/ENV 进镜像层。

### M15 · 机制演示
- **行为：** MockLLM 驱动、零网络的确定性演示脚本/测试。
- **输出：** 四个演示（见 §16.4）确定性通过。

---

## 7. 非功能性需求

### 7.1 性能（仅量化可确定性测的项）
- 单个命令执行受 `command_timeout_sec`（默认 30s）超时控制。
- 工具输出超 `output_max_bytes`（默认 64KiB）被截断，`truncated=true`。
- 单轮 LLM 调用失败自动退避重试 3 次。
- **不设**依赖真实 LLM/环境的响应时间指标（不可确定性测）。

### 7.2 安全
- 治理护栏、路径围栏、命令词法治理、脱敏器、审批状态机全部为确定性代码，移除真实 LLM 后可单测（见 §16）。
- 凭据威胁模型见 §12。
- 云端公网 demo 用演示沙箱限制执行面（见 M14）。

### 7.3 可用性
- 一键 `docker run` 起服务；CLI `demo` 一键跑机制演示；`make test` 一键测试。
- 冷启动流程在 README 可复现（§4.5 陌生 agent 验证）。

### 7.4 可观测性
- 每轮动作/判定/反馈/停机均落 SQLite 并可经 WebUI 查看。
- 审计事件流带哈希链，可校验完整性。

---

## 8. 系统架构

### 8.1 分层
```
WebUI (原生 HTML/CSS/JS)
   ↓
REST API (FastAPI)
   ↓
Application Service
   ↓
AegisCode Harness Core
   ├─ 主循环 (Orchestrator)
   ├─ LLM 抽象层 (LLMClient: OpenAI / Anthropic / Mock)
   ├─ 动作解析器 (Action Parser)
   ├─ 工具注册与分发 (Tool Registry / Dispatcher)
   ├─ 治理引擎 (Policy Engine: 命令治理 + 路径围栏 + 四档判定)
   ├─ 审批状态机 (HITL)
   ├─ 反馈闭环 (Feedback Collector / Classifier / Sanitizer)
   ├─ 记忆与上下文 (Memory Store / Context Builder)
   ├─ 审计 (Audit Log + Hash Chain)
   └─ 配置加载 (Config Loader)
   ↓
存储: SQLite + 文件系统(.aegis/snapshots)
```
CLI 也调用同一 Application Service / Core。

### 8.2 数据流（单轮）
构建上下文 → 调 LLM → 解析 1 个 Action → 治理判定（四档）→（REQUIRE_APPROVAL 时暂停等裁决）→ 工具执行 → 反馈分类 + 脱敏回灌 → 落盘（steps / audit_events）→ 停机判定。

### 8.3 外部依赖
- LLM 供应商：OpenAI-compatible chat completion API / Anthropic messages API（单次补全，不使用其 agent runner）。
- 运行时：Docker;OS keyring（可选，不可用则降级）。
- 库：FastAPI、Pydantic v2、标准库 sqlite3、pytest、PyYAML、keyring。

---

## 9. 数据模型（SQLite,6 表）

| 表 | 关键字段 |
|---|---|
| `tasks` | task_id(PK), workspace_path, workspace_hash(=project_id), task_description, state, termination_reason, step_count, created_at, updated_at |
| `steps` | step_id(PK), task_id(FK), step_index, action_json, governance_decision, triggered_rule_id, tool_result_json, feedback_category, created_at |
| `approval_requests` | approval_id(PK), task_id(FK), step_index, action_snapshot_json, action_fingerprint, governance_decision, triggered_rule_id, reason, risk_explanation, state, remember_choice, created_at, decided_at, decided_by |
| `audit_events` | event_id(PK), task_id(FK), step_index, timestamp, event_type, payload_json（已脱敏）， prev_hash, hash |
| `memories` | memory_id(PK), project_id, type, key, value, tags_json, source, confirmed, created_at, last_used_at, use_count |
| `task_snapshots` | snapshot_id(PK), task_id(FK), step_index, file_path, snapshot_path, created_at（回滚索引，Should） |

**说明：** `steps` 是粗粒度循环状态快照（便于恢复/查询）；`audit_events` 是细粒度 append-only 哈希链证据流。凭据（keyring/.env）与配置（YAML）不入库。

## 10. 领域与机制设计（§A.5 要求的独立章节）

本章回答 §A.3 的四类机制在 coding 领域的具体形态，并对每个机制标注**由确定性代码实现**与**MockLLM 下如何验证**。

### 10.1 Coding Agent 需要哪些工具

见 §6 的 M4：`list_files` / `read_file` / `search_text` / `write_file` / `run_tests` / `run_command` / `finish` 共 7 个。文件读写与命令执行是 Agent 作用于外部世界的两个出口，也是治理的两个焦点。

### 10.2 什么客观信号判断行为是否正确（反馈信号）

- **pytest 结果**（MVP 核心）：解析通过/失败数、失败测试名、断言行、traceback。
- **命令退出码**：非零即失败。
- **文件变更范围检查**：写入前后 diff，判断是否改了预期文件、是否超出允许范围。
- （Should）ruff / mypy 结果。

这些信号由**确定性校验器/传感器**（`FeedbackClassifier`）解析并分类为 8 类失败之一，回灌主循环。**MockLLM 验证**：构造 pytest 输出样本 → 断言分类正确；不需要真实 LLM。

### 10.3 哪些操作属于危险动作

- **直接 DENY**：`rm -rf`、`sudo`、`su`、`chmod`、`chown`、`curl`、`wget`、`git push`、`git reset --hard`、`git clean`、`python -c`/`python -m <inline>`、任意 shell 元结构（管道/重定向/命令替换/子 shell/后台）、路径穿越、符号链接逃逸、敏感文件读写、允许列表外的 argv0。
- **REQUIRE_APPROVAL**：`pip install`、`git commit`、写入 `write_allowlist_dirs` 之外的工作区内目录。

### 10.4 跨会话需要记住什么 / 不得记住什么

- **记住**：项目约定、用户设定的限制、历史设计决策、已批准的动作指纹、代码库基础事实。
- **不得记住**：API Key、`.env` 内容、凭据、大段工具原始输出、完整敏感源码、未经确认的 LLM 推测（`source=agent` 记忆标 `confirmed=false`，仅作提示、永不作治理依据）。

### 10.5 重点维度与理由

**重点维度 = 治理**（§11 详述）。理由：治理是六维度中确定性代码占比最高、演示最干净、最难用提示词规避的维度，最契合 §A.4（C） 的评分判据。

### 10.6 每个机制如何由确定性代码实现（汇总）

| 机制 | 确定性代码 | MockLLM 验证 |
|---|---|---|
| 动作解析 | JSON 提取 + Pydantic 校验 | 构造畸形/合法动作断言解析结果 |
| 命令治理（甲） | 5 层管线（shlex + 规则表） | 构造命令字符串断言判定 |
| 路径围栏（乙） | realpath + 归属判定 | 构造穿越/软链路径断言 DENY |
| 反馈分类 | 校验器解析输出 | 构造工具输出断言分类 |
| 审计哈希链 | SHA256 链 + verify_chain | 写入后篡改断言 verify 失败 |
| 停机判定 | 计数器 + 优先级规则 | 构造轮次序列断言终止原因 |
| 记忆读写 | SQLite + 脱敏过滤 | 写入含 key 内容断言被拒 |

## 11. 治理与安全护栏：主要贡献（独立章节）

本项目的 main contribution。治理引擎把安全判定从"提示词嘱托"变成确定性、可单测、可审计的策略代码。

### 11.1 治理引擎骨架

- **四档判定**：`ALLOW` / `ALLOW_WITH_AUDIT` / `REQUIRE_APPROVAL` / `DENY`。
- **求值结构**：有序 `PolicyRule` 列表，**first-match-wins**，每次判定产出唯一 `rule_id + reason`，喂给审计与反馈。
- **默认档（fail-closed，按动作类别分层）**：只读工具默认 ALLOW；写工具默认 REQUIRE_APPROVAL（`write_allowlist_dirs` 内默认 ALLOW）；命令不在允许列表默认 DENY。
- **四档执行语义**：ALLOW=立即执行并审计；ALLOW_WITH_AUDIT=执行并强化审计（记 rule_id+reason）；REQUIRE_APPROVAL=暂停、存动作快照、转 APPROVAL_REQUIRED；DENY=不执行、产出 POLICY_DENIED 反馈。

### 11.2 甲 · 命令词法治理（5 层确定性管线）

命令以**字符串**输入，流过：
1. **词法解析层**：`shlex` 解析为 token，失败 → INVALID_ACTION。
2. **结构安全层**：检测管道 `|`、重定向 `> >> <`、串联 `; && ||`、命令替换 `$() \`\``、子 shell `()`、后台 `&`、通配注入 → 一律 DENY。
3. **允许列表层**：提取 argv0，不在配置白名单 → DENY。
4. **危险参数层**：参数级规则（见 §10.3 划线，含 `python -c`/`-m` 拦截）→ DENY 或 REQUIRE_APPROVAL。
5. **执行层**：`subprocess` + `shell=False` + argv 数组 + 超时 + 输出上限 + cwd 锁工作区，**永不 `shell=True`**。

**确定性 + MockLLM 验证**：每层可独立单测；演示①用 MockLLM 发 `"rm -rf /"` 字符串断言 DENY。

### 11.3 乙 · 路径围栏

见 §6 M6 与 §10.3。核心：**先 realpath 解析（解掉 `..` 与符号链接）再判归属**；新建文件对父目录做归属判定 + 校验文件名非软链。演示③用逃逸软链断言 DENY。仅支持 Linux。

### 11.4 HITL 人工审批状态机

- **两层状态**：TaskState（CREATED→RUNNING⇄APPROVAL_REQUIRED→COMPLETED/FAILED/CANCELLED）+ ApprovalState（PENDING→APPROVED/REJECTED/EXPIRED/SUPERSEDED）。
- **ApprovalRequest 字段**：action_snapshot、action_fingerprint、governance_decision、triggered_rule_id、reason、risk_explanation、state、remember_choice、时间戳、decided_by。
- **边界规则**：动作指纹变 → SUPERSEDED 重审；审批无超时（EXPIRED 预留）；"记住批准"限完全相同指纹（MVP 做）；恢复只执行原始动作快照；用户拒绝 → APPROVAL_REJECTED 反馈回灌、继续、计入连续失败。

### 11.5 审计与哈希链

见 §6 M8。每任务 append-only 事件流（7 类 event_type），`hash=SHA256(prev_hash‖规范化本条)`，只做可检测篡改（不做 HMAC 签名，签名为未决/未来项），确定性 `verify_chain(task_id)`。写入前脱敏。

### 11.6 回滚（Should）

写前快照到 `.aegis/snapshots/<task_id>/<step>/` + `rollback_task(task_id)` 逆序恢复。纯文件复制，确定性可测。

## 12. 凭据威胁模型

调用真实 LLM 需安全管理 API Key。威胁与确定性对策：

| 威胁 | 对策（确定性机制） |
|---|---|
| 硬编码进源码 | 代码零 key 常量 |
| 提交进 Git（含历史） | `.gitignore` 含 `.env`/`.aegis/`；自写 secret 扫描器 + CI gitleaks 双保险 |
| 日志 / 审计 / 反馈泄漏 | 全局脱敏器覆盖，key 正则擦除 |
| 错误堆栈泄漏 | 异常不打印 key；凭据读取失败只报"未配置" |
| WebUI 回显 | `/credentials/status` 只返 `configured:bool` + 掩码，**永不明文** |
| shell history | 禁止命令行 `export`；`key set` 用 getpass 隐藏输入 |
| 环境变量泄漏 | 明示进程环境可见风险；作为优先级 3 来源 |
| Docker 镜像层 | key 绝不 COPY/ENV 进镜像，运行时注入 |
| 配置文件权限 | `.env` 写入 `chmod 600` |
| 测试泄漏 | stub keyring（内存）+ 假 key（`sk-test-fake`），永不联网 |

**存储分层降级**：keyring（默认）→ `.env`（`.gitignore` + chmod 600，默认关闭，需显式 `allow_dotenv:true` + 明文警示）→ 环境变量（Docker/CI 注入）。**读取顺序同上**。

**录入 / 更新 / 清除**：`aegiscode key set`（getpass 隐藏录入）/ `key status`（掩码，不回显明文）/ `key clear`（清除）。

## 13. 凭据与分发设计

### 13.1 分发形态

**Docker 单一形态**（MVP）。PyPI / 原生二进制 → 未来。

- `docker build` 一条 + `docker run` 一条即可启动（FastAPI + WebUI）。
- 推送公开 registry（Docker Hub / GHCR）。
- key **绝不进镜像**，运行时通过 `-e` 或挂载 `.env` 注入。
- workspace 通过 `-v /host/project:/workspace` 卷挂载。

### 13.2 容器内凭据处理

容器通常无 OS Secret Service。检测到 keyring 后端不可用时**自动回退到环境变量**（不崩溃）。环境变量注入不受 `allow_dotenv` 开关限制（该开关只管 `.env` 文件）。

### 13.3 冷启动流程（新机器从零运行）

1. `docker run` 起服务（或本地 `pip install -e . && aegiscode serve`）。
2. 配 key：本地 `aegiscode key set` / 容器 `-e OPENAI_API_KEY=...`。
3. 浏览器打开 WebUI → 选 workspace + 提任务 → 观察 / 审批 → 看结果。

### 13.4 云部署（公网 demo URL，§清单第 9 条硬性）

- 候选平台：Render / Railway / Fly.io（有免费额度，支持 Docker）。
- **安全形态 = 演示沙箱**：workspace 锁定为镜像内预置玩具 Python 项目；`run_command` 允许列表收到最窄；LLM 用 **MockLLM 跑固定脚本**（零成本零风险）。
- 零门槛访问，不强制口令。
- **澄清**：主场景是"本地自带 key 的 harness"（零鉴权，正常用法）；公网 demo 只是受限橱窗——沙箱限制"进来能造多大破坏"，MockLLM 免除烧钱风险。

## 14. 技术选型与理由

### 14.1 语言与框架

**Python 3.12 全家桶。**

| 组件 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.12 | 见 14.2 |
| Web 框架 | FastAPI | 异步、Pydantic 原生集成 |
| 数据校验 | Pydantic v2 | 动作协议 / 配置 / ToolResult schema |
| 存储 | 标准库 `sqlite3` + 手写 SQL | 零 ORM 依赖、透明、记忆存储"自实现"更纯粹 |
| 测试 | pytest | MockLLM 注入 + monkeypatch 最省事 |
| 配置 | PyYAML | 声明式配置 |
| 凭据 | `keyring` | 跨平台 OS 钥匙串 |
| 命令词法 | 标准库 `shlex` | **甲核心：Python 标准库直接可用** |
| 路径 | 标准库 `pathlib` / `os.path` | **乙核心：realpath 完善** |
| 分发 | Docker | 规避 Python 二进制分发弱的劣势 |
| 前端 | 原生 HTML/CSS/JS | 豁免 Open Design（纯功能观测 + 审批界面） |

### 14.2 为什么 Python（对比 TypeScript / Go）

关键判断：**甲核心（命令词法治理）依赖 shell 词法分析，`shlex` 是 Python 标准库**（TS/Go 都需第三方库），这一条几乎单独决定选型。此外：乙核心 pathlib realpath 顺手；MockLLM + 确定性单测（评分命脉）用 pytest+依赖注入最省事；Pydantic/keyring/FastAPI 生态成熟。Python 唯一劣势（单文件二进制弱）在已选 Docker 分发后被规避；Go 的二进制优势因此失效，TS 各项均需凑第三方。

### 14.3 LLM 抽象层与供应商

统一 `LLMClient` 接口（输入=消息列表+参数，输出=文本）；三个实现：`OpenAIAdapter`（chat completions，可配 base_url 兼容 DeepSeek/通义/vLLM）、`AnthropicAdapter`（messages API）、`MockLLM`。协议差异（角色映射、system 处理、响应字段）封装在各适配器内，**主循环与治理/反馈完全不感知用的哪个厂商**——印证"LLM 抽象层可替换"。

### 14.4 前端豁免 Open Design 的理由

通用要求 §3.6"涉及 UI 强烈推荐 Open Design"。AegisCode 的 WebUI 本质是**只读观测 + 审批面板**（治理是主角，UI 是配角）。采用极简原生 HTML/CSS/JS，避免设计系统开销挤占治理深度实现时间。

## 15. 验收标准

SPEC 保持模块级验收（每模块 1~2 条客观可断言条件），细粒度验证步骤留给 PLAN 的每个 task。每条均应可自动化断言。

| 模块 | 验收条件 |
|---|---|
| **M1 主循环** | 单动作循环可运行；达 max_steps 记 MAX_STEPS；连续失败达 M、NO_PROGRESS 达阈值各自停机（单测）。finish 触发独立最终验证，验证不过不判 COMPLETED。 |
| **M2 LLM 抽象层** | MockLLM 零网络驱动全流程；OpenAI/Anthropic 适配器接口一致性测试通过。 |
| **M3 动作协议** | 合法 JSON 正确解析；畸形/缺字段/未知工具 → INVALID_ACTION；连续 3 次无效 → 停机（单测）。 |
| **M4 工具分发** | 7 工具注册可查找；参数校验；结果标准化为 ToolResult；未知工具报错（单测）。 |
| **M5 治理·甲命令** | rm -rf / sudo / git push / python -c 等 → DENY；管道/重定向/命令替换/子 shell → DENY；pip install → REQUIRE_APPROVAL；允许列表外 argv0 → DENY（逐条单测）。 |
| **M6 治理·乙路径** | ../ 穿越、绝对路径越界、符号链接逃逸 → DENY；敏感文件 → DENY；新建文件父目录判定正确（逐条单测）。 |
| **M7 审批状态机** | REQUIRE_APPROVAL 暂停；批准→执行原始快照；拒绝→反馈继续；指纹变→SUPERSEDED；"记住批准"生效（单测）。 |
| **M8 审计** | 每动作产生事件；verify_chain 正确；篡改任一条 → verify 失败；payload 已脱敏（单测）。 |
| **M9 反馈闭环** | pytest 结果正确分类；失败反馈截断脱敏后进入下一轮 messages；重复动作 → NO_PROGRESS（单测）。 |
| **M10 记忆** | 写入过脱敏器（key 被拒）；检索按 type+project+关键词+topK；source=agent 记忆 confirmed=false 不作治理依据（单测）。 |
| **M11 配置** | YAML 加载 + Pydantic 校验；非法配置启动即报错；改配置改变判定（单测）。 |
| **M12 凭据** | key set/status/clear 工作；status 不回显明文；secret scanner 检出植入的假 key（单测）。 |
| **M13 WebUI/API** | 8 端点可用；创建任务→轮询事件→审批→看结果走通；credentials/status 掩码。 |
| **M14 分发** | docker build + run 一条起服务；冷启动流程 README 可复现；云端 demo URL 可访问。 |
| **M15 机制演示** | 三个（+1 附加）演示脚本确定性通过。 |

**非功能验收**（只量化可确定性测的项）：单工具执行受 `command_timeout_sec` 超时控制（可测）；工具输出超 `output_max_bytes` 被截断（可测）；LLM 调用失败自动重试 3 次（可测）。**不设**依赖真实 LLM / 环境的响应时间类指标。

## 16. 确定性机制与 MockLLM 测试策略

### 16.1 判定标准（§A.4C）

harness 每个核心机制（工具分发、治理拦截、反馈回灌、记忆读写、停机、审计、动作解析），替换为 MockLLM 后**仍能用确定性单元测试验证**。凡离开真实 LLM 就无法测试者，不计入 harness 实现。

### 16.2 MockLLM 设计

`MockLLM(scripted_responses)`：按调用顺序返回预设响应队列（通常是动作 JSON）；记录每次收到的 `messages`（用于断言"失败反馈确实进入了下一轮上下文"）；零网络、零 key。条件响应（如"看到 TEST_FAILURE 就返回修正动作")仅个别高级测试用简单 lambda，MVP 主要用按序队列。

### 16.3 测试分层

| 层 | 测什么 | 依赖 |
|---|---|---|
| 单元测试 | 治理规则、路径围栏、命令词法、反馈分类、脱敏器、哈希链 verify、停机判定、动作解析 | 无 LLM、无网络 |
| 集成测试 | 主循环 + MockLLM 多轮：黄金路径、审批暂停恢复 | MockLLM |
| 机制演示 | §16.4 四个演示 | MockLLM |

测试入口：`make test` 一键运行；CI 含名为 `unit-test` 的 job（§清单第 6 条）。

### 16.4 机制演示（§A.6 硬性，MockLLM 驱动、零网络）

- **演示①（治理拦截危险动作）**：MockLLM 返回 `{tool:run_command, arguments:{command:"rm -rf /"}}`。断言：词法解析 → 命令规则命中 → DENY；工具执行次数=0；文件系统无变化；审计有 GOVERNANCE_DECISION=DENY 带 rule_id；Agent 收到 POLICY_DENIED 反馈。
- **演示②（失败反馈驱动动作变化）**：预设轮1 write_file（错误实现）→轮2 run_tests→（失败）→轮3 write_file（与轮1不同的修正）→轮4 run_tests→（通过）→轮5 finish。断言：轮2 后 TEST_FAILURE 出现在轮3 传给 MockLLM 的 messages 里；轮3 动作 ≠ 轮1；最终 finish 触发的独立验证通过；**COMPLETED 由最终验证器复跑绿而非 MockLLM 声称**。
- **演示③（路径围栏·符号链接逃逸被拒）**：临时工作区内建软链 `evil -> /etc/passwd`；MockLLM 返回 `{tool:read_file, arguments:{path:"evil"}}`。断言：realpath 归属判定失败 → DENY；未读到工作区外内容；审计记录。
- **演示④（附加·SUPERSEDED 重审）**：体现审批治理深度——动作指纹变化后旧审批失效需重审（确定性单测）。

**黄金路径端到端集成测试**（演示②超集）：pip install 被拒 → 改标准库 → 测试失败 → 修正 → 通过 → finish → 最终验证绿。

## 17. 风险、限制与未决问题

### 17.1 技术/实现风险

| 编号 | 风险 | 缓解 |
|---|---|---|
| R1 | 命令词法治理绕过（允许列表内程序作恶，如 `python -c`） | 已将 `python -c` / `python -m <inline>` 加入 command_rules 审批/拒绝清单 |
| R2 | realpath 的 TOCTOU（判定通过后、执行前软链被替换） | 单用户本地场景风险极低；写入已知限制，MVP 不处理 |
| R3 | SQLite 并发（异步后台任务 + API 查询并发写） | MVP 单任务串行；WAL 模式 + 短事务 |

### 17.2 范围/进度风险

| 编号 | 风险 | 缓解 |
|---|---|---|
| R4 | 为六维度完整而牺牲治理深度 | PLAN 优先实现"治理+反馈垂直切片跑通黄金路径"，其余维度最小实现 |
| R5 | 冷启动验证（§4.5）暴露 SPEC 缺陷 | 这是预期结果而非失败；受阻点记入 SPEC_PROCESS.md |

### 17.3 评分对齐风险

| 编号 | 风险 | 缓解 |
|---|---|---|
| R6 | "机制是代码不是提示词"未持续自检 | 每机制实现时自问"移除 LLM 还能单测吗"，由 §16 覆盖 |
| R7 | REFLECTION.md 须本人撰写（§六禁止 AI 代写） | 学术规范提醒，AI 仅辅助润色并标注 |

### 17.4 已知限制（写入 SPEC，MVP 不解决）

- 仅支持 Linux 路径语义（Windows 大小写折叠不处理）。
- 仅支持 Python + pytest 单栈。
- 不提供通用 shell 的完整安全化（元结构一律 DENY，不解析复杂 shell）。
- 单任务串行，无并发。
- 回滚为 Should 档，可能不进入首版。

### 17.5 未决问题（留待实现阶段决定，不阻塞 SPEC）

以下为**尚未最终拍板**的问题，标记为未决，不在本 SPEC 中猜测结论：

- **UQ1**：`ContextBudget` 的 `context_budget_chars` 默认值（暂列 24000）需在实现期结合真实 prompt 体量校准。
- **UQ2**：`command_allowlist` 的最终默认成员清单（示例列了 python/pytest/ruff/mypy/git/ls/cat）需在实现期依黄金路径确认。
- **UQ3**：确定性"摘要化最旧轮"的具体压缩规则（保留哪些字段、丢弃哪些）需在实现期定义并单测。
- **UQ4**：云端 demo 沙箱预置的玩具 Python 项目的具体内容与目标测试。
- **UQ5**：`write_max_bytes` / `output_max_bytes` / `command_timeout_sec` 的默认数值需实测校准。
- **UQ6**：Anthropic 与 OpenAI 两适配器的消息角色映射细节（system 处理、多轮拼接）需在实现期对齐各自 API。

---

## 附录 A：决策溯源

本 SPEC 的每一项决策均来自 `SPEC_PROCESS.md` 第 1~25 轮的逐轮讨论记录（含被否决方案与分歧记录）。三处用户推翻/修正智能体推荐的关键节点：绝对路径策略（第 13 轮）、Agent 写记忆（第 16 轮）、云部署鉴权场景澄清（第 19 轮）。

**本文档为设计规约，不含实现代码。实现须待 PLAN.md 产出后，按 TDD 红-绿-重构进行。**

---

## 附录 B：真实 LLM Provider 可用性（课程要求之外的追加实现 / Enhancement）

> **定位声明（重要）**：本附录描述的能力是**课程要求之外的追加实现（enhancement）**。课程评分口径（§A.4C）只要求"移除真实 LLM 后每个核心机制可用 MockLLM/stub 确定性单测验证"，AegisCode 主体已满足。**课程从未强制要求真实 LLM 端到端测试。** 本附录让真实 Provider（OpenAI / Anthropic / OpenAI 兼容端点如 DeepSeek/通义/vLLM）能够真正驱动 Harness 完成编码任务；默认测试仍以 MockLLM 为准，真实 LLM 测试不进入 `make test` 与普通 CI。

### B.1 追加动机（真实 CLI 当前失败的直接原因）

主体实现中，`HarnessCore._build()` 以 `system_prompt=""`、`tool_protocol=""` 调用 `build_context`。MockLLM 按脚本回放不受影响（故 §16 全部确定性测试与四演示通过），但真实模型**只收到任务文本**——没有身份、没有动作 JSON 协议、没有工具清单、没有工作区规则。真实模型无从得知必须输出 `{tool, arguments}` 结构化动作，其散文输出每轮触发 `ActionParseError` → `INVALID_ACTION` 反馈，直至 `action_retry_limit` / `max_steps` 停机，永远不会创建文件。**追加实现的核心即：由 Harness Core 构造完整、Provider 无关的上下文。**

### B.2 PromptBuilder（Provider 无关，新增 `aegiscode/prompt/builder.py`）

Harness Core 使用**唯一的** `PromptBuilder`，不在各 Adapter 中复制提示词。以 `(config, registry)` 构造，产出两段文本，经既有 `build_context(system_prompt, tool_protocol, ...)`（签名不变）装配为 messages。

- **`system_prompt(remaining_steps)`** 必须明确：
  - 模型是运行在 AegisCode 中的 coding agent；
  - 不能直接访问文件系统和 Shell——一切副作用只能经工具（参数校验 → 治理 → 执行 → 审计）；
  - 每轮只能返回**一个**合法结构化动作；
  - 只能使用当前 Tool Registry 中**启用**的工具；
  - 只能操作当前 workspace；禁止路径穿越、绝对路径、`.git`、`.env`、`*.pem`/`*.key`、`*credentials*`（从 `config.governance.sensitive_file_patterns` 渲染）；
  - 命令允许列表与规则（从 `config.governance.command_allowlist` + `command_rules` 具体渲染：如 `pip install`→审批、`git push`/`git reset --hard`/`python -c`/`python -m`→拒绝。注意 `rm`/`sudo`/`curl` 等不在允许列表内，故不作为 `command_rules` 渲染，而是通过"argv0 不在 allowlist → DENY"拦截，允许列表同样渲染进提示词）；
  - 工具失败、治理拒绝、解析错误、pytest 失败后必须依据反馈调整下一步；
  - 不能声称执行了未实际执行的动作；
  - **只有 pytest 客观通过后才能输出 `finish`**；
  - 剩余步数 `remaining_steps`。
- **`tool_protocol()`** 复用**既有 Action Parser 协议**（不新建第二套）：`Action = {thought?, tool, arguments, expectation?}`，单个 ```json 围栏对象；随后逐工具块**从 live registry 动态生成**（工具名、功能、参数 Schema、必填字段、当前限制）。**被禁用的工具因未注册而结构性缺席，不会出现在提示词中。**

### B.3 工具元数据（描述来自 Tool Registry）

7 个工具类各新增声明式 `description: str` 与 `parameters: dict`（字段名 → {类型、必填、说明}），字段与各 `run()` 实际从 `arguments` 读取的键**同源**（如 `write_file`→`path`,`content`；`run_command`→`command`；`search_text`→`query`）。`ToolRegistry.describe()` 遍历**已注册**工具渲染规格。由于 `assembly._build_registry` 只注册 `config.tools.enabled` 的工具，"启用集合"已在 registry 结构中，无需第二份易漂移的旁路目录。

### B.4 上下文与错误处理

每轮上下文（经 `build_context`）包含：system prompt、用户任务、当前允许的工具、workspace 约束、前序动作、工具结果、治理反馈、pytest 反馈、必要且脱敏的项目记忆、剩余步数。既有反馈闭环（`harness.py`：`POLICY_DENIED` / `TEST_FAILURE` / `TOOL_ERROR` / `PARSE_ERROR` / `SUPERSEDED` 均回灌 `last_feedback` 与 `recent_steps`）**保持不变**——追加实现只补全出站提示词。

真实模型输出不合法时（既有行为，追加实现依赖之）：不得猜测并执行文本中的命令；不得执行部分解析结果；将具体解析错误作为结构化反馈进入下一轮；连续失败达上限后按现有 stop condition 终止。

### B.5 Adapter 与 CLI

`OpenAIAdapter`、`AnthropicAdapter` 只负责：按供应商格式发送 system prompt 与 messages；使用可配置的 model、base_url、超时；返回模型响应；标准化认证/限流/超时/格式错误。**不得**自维护 Agent Loop、不得自行执行工具、不得自定治理策略。

追加改动：`AnthropicAdapter` 增加可配置 `base_url`（默认 `https://api.anthropic.com`），`assembly.build_llm` 一并传入 `config.llm.base_url`（`OpenAIAdapter` 已支持）。CLI 通过 `config.llm.provider` 明确选择真实 Provider，同时保留 `mock` 模式；配置了 Key 也不会让 `make test` 调用真实 LLM（测试从不选择真实 Provider）。日志只显示 Provider / Model / 凭据已配置或未配置，绝不显示 API Key、Authorization Header 或完整敏感请求。

### B.6 确定性自动测试（零真实网络）

至少覆盖：PromptBuilder 含身份/工具协议/workspace 边界/完成条件；工具描述来自 Tool Registry；禁用工具不暴露；提示词不含 Secret；OpenAI 与 Anthropic 请求正确携带 system prompt；自定义 base_url 与 model 正确传递；合法工具动作与 finish 可解析；非 JSON/多动作/未知工具/缺失参数被拒；解析错误进入下一轮；工具结果、治理反馈、pytest 失败进入下一轮；pytest 未通过时不能 finish；pytest 通过后可正常结束。`make test` 与 `make demo` 全部通过且不访问真实 LLM。

### B.7 真实 LLM 端到端测试（人工触发，`make e2e-real-llm`）

`scripts/e2e_real_llm.py`：使用全新空临时工作区，经**真实 CLI 路径**（`build_service` → HarnessCore）提交固定任务（创建 `add.py`/`test_add.py`、pytest 全通过后方可声明完成）。须证明：使用了真实 Provider 而非 MockLLM；两文件由 Harness 工具创建；动作经解析、治理、工具分发；pytest 结果进入 Harness；最终完成依赖 pytest 通过；工作区外无副作用；日志无 Secret。该命令使用临时工作区、不硬编码正确源码、**不进入默认 `make test`、不进入普通 CI**、失败返回非零退出码、输出脱敏。运行真实 Provider 可能产生 API 费用。

### B.8 完成条件

Harness Core 构造完整 system prompt；工具协议从 Tool Registry 动态生成；每轮只允许一个结构化动作；非法输出会收到反馈；pytest 未通过时不能 finish；Adapter 正确传递 system prompt；CLI 可选择真实 Provider；API Key 不进入日志；`make test` 通过；`make demo` 通过；真实 CLI 能在空工作区创建 `add.py` 与 `test_add.py`；`python -m pytest -q` 通过；工作区边界有效；review 无未处理 Critical / Important 问题。

> **向后兼容**：`PromptBuilder` 作为 `HarnessCore` 可选构造参数注入，缺省 `None` 时回退空提示词，既有 419 项测试与四演示不受影响。

### B.9 追加改进：收尾引导 + e2e 可观测性（来自首次真实运行的反馈）

首次人工真实运行（DeepSeek）暴露两点真实问题，本节记录对应改进（仍属附录 B enhancement 范畴，均确定性零网络可测）。

**背景（真实运行轨迹）**：模型正确地写文件、被治理 DENY 了 `python -m pytest`、据反馈改用 `pytest -q` 并通过——但随后**未 `finish`，反而反复重写相同 `add.py`**，触发 NO_PROGRESS 停机 → 任务 FAILED。治理/审批/反馈/停机机制全部正确工作；问题在真实模型不知道"测试通过后该收尾"，且 e2e 脚本只打印 5 个 PASS/FAIL 符号、未展示这条过程。

**改进 1 · PromptBuilder 收尾引导**（`aegiscode/prompt/builder.py`，`system_prompt` 增补两条规则）：
- 不要重复已成功的动作——文件已写对、命令已成功就不要再发一遍；harness 会把重复的相同动作判为无进展（NO_PROGRESS）并停机。
- 测试一旦客观通过，下一个动作**必须**是 `finish`，不要再重写已经正确的文件。
- 确定性测试：断言 `system_prompt()` 含"不重复成功动作"与"测试通过后立即 finish"的引导；既有 no-secret / 边界断言保持通过。

**改进 2 · e2e 可观测性**（`scripts/e2e_real_llm.py`，`verify()` 签名不变、离线守卫不受影响）：
- `format_trace(events)`：逐步打印 `step N | 动作(tool+参数摘要) | 治理判定(decision+rule+reason) | 反馈类别`，末尾打印 `TERMINATION reason`。
- `print_generated_files(workspace)`：打印 `add.py`/`test_add.py` 实际内容。
- `main()` 在验收摘要前打印完整轨迹 + 文件内容，全程复用脱敏器（不泄漏 Key）。
- 确定性测试：用手搓假 events 调 `format_trace`，断言输出含动作/治理判定/终止原因等关键行（捕获 stdout）。

**不改**：CLI、治理引擎、`make test` / CI 隔离、`verify()` 的 5 项布尔契约。