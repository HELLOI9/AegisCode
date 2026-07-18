# AegisCode

[![CI](https://github.com/HELLOI9/AegisCode/actions/workflows/ci.yml/badge.svg)](https://github.com/HELLOI9/AegisCode/actions/workflows/ci.yml)

> 治理优先的编码智能体 harness —— 自实现主循环 + 确定性反馈闭环。
> A policy-governed coding-agent harness with deterministic feedback loops.

## 1. 项目简介

AegisCode 是一个**治理优先**的编码智能体运行时(coding-agent harness)。它不是又一个"让 LLM 自由改代码"的工具,而是把**每一个** LLM 提议的动作都送进一道治理闸门:命令词法治理(甲)、路径围栏(乙)、四档判定(ALLOW / ALLOW_WITH_AUDIT / REQUIRE_APPROVAL / DENY)、人类在环审批(HITL)与 SHA256 审计哈希链。危险动作在**执行前**被拦截,高风险动作暂停等待人工批准,且批准被绑定到动作指纹——改动过的动作会使旧批准失效。

第二支柱是**完整的反馈闭环**:Agent 写代码 → 运行客观验证(pytest / 命令退出码 / 文件变更范围)→ 失败被标准化后回灌进下一轮上下文 → Agent 据客观信号自我修正 → 完成由**客观复验**判定,而非 LLM 自称完成。

关键约束:**Agent 主循环由本项目自行实现**(不依赖任何现成 Agent SDK / 宿主智能体循环),且所有核心机制在替换为 MockLLM 后**仍能用不依赖网络、不依赖真实 LLM 的确定性测试验证**。

## 2. 核心架构

```
LLM 抽象层 (OpenAI / Anthropic / MockLLM)
        │  结构化动作协议 (JSON: tool + arguments)
        ▼
   自实现 HarnessCore 主循环  (aegiscode/loop/harness.py)
        │
        ├─ 动作解析 (protocol/parser.py)
        ├─ 治理引擎 (governance/)
        │     ├─ 甲 命令词法治理  command_lexer + command_rules (最严者胜)
        │     ├─ 乙 路径围栏      path_fence (realpath + commonpath, 符号链接安全)
        │     ├─ 四档判定 + 默认判定  engine + factory
        │     ├─ HITL 审批状态机   approval (指纹绑定 / SUPERSEDED)
        │     └─ 工具分发         dispatcher (run_command 亦过路径围栏)
        ├─ 工具注册分发 (tools/: read/write/list/search/run_command/run_tests/finish)
        ├─ 反馈闭环 (feedback/: pytest 解析 + 失败分类 → 回灌下一轮)
        ├─ 记忆与上下文 (memory/: SQLite 检索 + 6 段预算装配, source=agent 永不作治理依据)
        ├─ 审计哈希链 (audit/: 脱敏 → SHA256 链, redact-before-hash)
        └─ 停机与防死循环 (loop/termination.py: 步数/连续失败/无进展/超时)
        │
        ▼
   持久化 (persistence/: 标准库 sqlite3 + 手写 SQL, 零 ORM)
   服务层 (service/: ApplicationService + REST API + 极简 WebUI + CLI)
   凭据 (credentials/: keyring → .env → env 分层, 状态仅掩码)
```

设计取舍与逐轮决策记录见 `docs/SPEC.md` 与 `docs/SPEC_PROCESS.md`。

## 3. 安装方式

要求 **Python ≥ 3.12**。建议用虚拟环境:

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"              # 含测试依赖 (pytest/ruff/mypy)
# 仅运行(不含开发依赖): pip install -e .
```

运行期依赖:`fastapi`、`uvicorn`、`pydantic`、`pyyaml`、`keyring`、`httpx`(见第 16 节许可证)。

## 4. 开发环境运行方式

```bash
# 生成一份带注释的默认配置(可选;所有字段都有安全默认值)
aegiscode init

# 运行一个任务(--workspace 是 Agent 的工作目录,--task 是任务描述)
aegiscode run --workspace ./sandbox --task "实现 add(a,b) 使测试通过" --watch

# 校验并查看当前配置摘要
aegiscode config

# 启动本地面板(见第 11 节)
aegiscode serve --host 127.0.0.1 --port 8000
```

`--workspace` 指定的目录即 Agent 的**工作区根**;路径围栏把所有文件动作限制在其内(见第 14 节)。MockLLM 模式下无需任何 API Key(见第 7 节)。

## 5. Docker 分发方式

```bash
# 构建镜像
docker build -t aegiscode .

# 以 MockLLM 模式启动(无需 Key),仅绑定到本机回环
docker run --rm -e AEGIS_LLM_PROVIDER=mock -p 127.0.0.1:8000:8000 aegiscode

# 以真实 LLM 运行:运行时用 -e 注入 Key(绝不烤进镜像层),挂载工作区
docker run --rm \
  -e OPENAI_API_KEY=sk-... \
  -v "$PWD/sandbox":/workspace \
  -p 127.0.0.1:8000:8000 aegiscode
```

镜像基于 `python:3.12-slim`,只 `COPY` 包元数据 + `aegiscode/` + `demos/`;`.dockerignore` 排除 `.env`、`*.pem`、`*.key`、`*.db`、`tests/`、`docs/` 等。**凭据绝不进镜像**,一律运行时注入。安全提醒:面板无鉴权,`-p` 请只映射到 `127.0.0.1`(见第 14 节)。

## 6. API Key 安全配置

Key 按 **keyring → `.env`(需显式开启)→ 环境变量** 分层解析,**从不硬编码、从不提交、从不记录**:

```bash
aegiscode key set        # 通过 getpass 安全录入(不回显、不入 shell 历史)
aegiscode key status     # 仅显示掩码(前 3 + … + 后 4);永不回显明文
aegiscode key clear      # 清除
```

清除后,若选择真实 provider 又无 Key,会以清晰错误安全拒绝(`no API key configured; run \`aegiscode key set\``),绝不触网、绝不泄漏。审计哈希链在计算 SHA256 与落库**之前**先脱敏(redact-before-hash),脱敏器覆盖 `sk-…`/`sk-proj-…`/`sk-svcacct-…`/`sk-ant-…`/AWS `AKIA…`/带引号的 `KEY="..."` 赋值等格式。

## 7. MockLLM 模式

MockLLM 是一个**完全离线、确定性**的 LLM 替身:按调用顺序回放预置响应,不触网、不需 Key。它是本项目"自实现 harness"命题的验证基础——所有核心机制(工具分发、治理拦截、反馈回灌、记忆读写、停机、审计、审批)在 MockLLM 下都能被确定性单测覆盖。

```bash
# 配置文件方式
echo -e "llm:\n  provider: mock" > aegis.yaml
# 或环境变量方式(无配置文件亦生效)
export AEGIS_LLM_PROVIDER=mock
```

`make test` 与 `make demo` 都**不需要真实凭据**。

## 7.1 真实 LLM Provider（课程要求之外的追加实现 / enhancement）

> 详见 `docs/SPEC.md` 附录 B 与本文件第 16 节。**课程从未强制要求真实 LLM 端到端测试**;默认与评分仍以 MockLLM 确定性测试为准。此为让真实模型可实际驱动 Harness 的追加实现。

配置 `aegis.yaml`(或环境变量 `AEGIS_LLM_PROVIDER`/`AEGIS_LLM_MODEL`)选择真实 Provider:

```yaml
llm:
  provider: openai        # openai | anthropic | mock
  model: gpt-4o           # 供应商模型 ID
  # base_url: https://api.openai.com/v1   # 可选:覆盖到本地/代理/兼容端点
```

- **provider**:`openai`、`anthropic` 或 `mock`。
- **base_url**:两个适配器都支持。OpenAIAdapter 会向 `{base_url}/chat/completions` 发请求,故 OpenAI 兼容端点(DeepSeek / 通义 / vLLM 等)填其 base(如 `https://api.deepseek.com`)即可;AnthropicAdapter 向 `{base_url}/v1/messages` 发请求,默认 `https://api.anthropic.com`。
- 适配器只负责传输(按供应商格式发送 system prompt + messages、可配 model/base_url/超时、标准化错误),**不**自维护 Agent Loop、不执行工具、不定治理策略。
- 真实运行前需 `aegiscode key set` 配置 Key。运行 `aegiscode run --workspace <dir> --task "..."` 即用真实模型驱动完整治理闭环。

**人工触发的真实 LLM 端到端测试**(需真实 Key + 网络,**可能产生 API 费用**):

```bash
make e2e-real-llm     # 使用临时工作区,不进 make test/普通 CI,失败非零退出,输出脱敏
```

该命令用真实 Provider 经 AegisCode 本地 harness 在全新临时工作区创建 `add.py`/`test_add.py`,证明动作经解析→治理→工具分发、pytest 结果进入 harness、最终完成依赖 pytest 通过、工作区外无副作用、日志无 Secret。若 `provider: mock` 会拒绝运行(退出码 2)。

## 8. 测试命令

```bash
make test        # = pytest -q,运行完整自动化测试套件
```

覆盖单元测试、Agent 主循环、MockLLM、工具分发、治理机制(命令/路径/审批)、反馈回灌、记忆、停机条件、REST API/WebUI 后端、以及不依赖网络的核心集成测试。

## 9. 机制演示命令

```bash
make demo              # 依次运行三项确定性机制演示(MockLLM,零网络,无需 Key)
# 单项(可选):
make demo-guardrail    # 仅 Demo 1
make demo-feedback     # 仅 Demo 2
make demo-approval     # 仅 Demo 3
```

`make demo` 在任一演示的契约检查失败时以**非零退出码**结束(绝不吞错返回成功),故可直接被 CI 门控。

## 10. `make demo` 的三项演示内容

每项都通过**真实的 HarnessCore**(而非桩)端到端驱动,并读回真实审计日志/磁盘状态/执行计数作为独立证据。

- **[Demo 1/3] 危险动作被治理护栏拦截** —— MockLLM 请求危险命令,治理判定 DENY,**工具执行次数为 0**,审计记录命中的策略(GOVERNANCE_DECISION=DENY + rule_id),Agent 收到结构化 POLICY_DENIED 反馈。
- **[Demo 2/3] 失败反馈驱动下一步动作改变** —— Agent 写出错误实现 → 真实子进程验证失败 → 失败标准化后进入下一轮上下文 → Agent 返回**不同的**修正动作 → 复验通过 → 完成由 `final_verifier` **客观复跑**判定(非 LLM 自称)。
- **[Demo 3/3] 审批绑定与失效** —— 高风险动作触发 REQUIRE_APPROVAL,harness 暂停(**暂停时执行次数为 0**);批准**原始**动作后其得以执行;随后参数被改动,复用旧批准时指纹分歧 → **SUPERSEDED**,改动后的动作**不执行**、重新走判定;审计完整记录 APPROVED→SUPERSEDED 全过程。

输出为逐行 `PASS:`,并以 `AegisCode mechanism demos: 3 passed, 0 failed` 收尾。

> 注:CLI 另有 `aegiscode demo`,运行 SPEC §16.4 的四个机制演示(含路径围栏符号链接逃逸)。`make demo` 是**评分入口**(恰好三项 + 退出码语义);`aegiscode demo` 是随镜像发布、可在容器内直接跑的 SPEC 演示。

## 11. WebUI 使用方法

```bash
aegiscode serve --host 127.0.0.1 --port 8000
# 浏览器打开 http://127.0.0.1:8000
```

极简单页面板:提交任务、查看任务状态/步骤事件流、查看并处理待审批(approve/reject)、查看凭据状态(仅掩码)。所有渲染走 `textContent`(XSS 安全)。REST API 端点见 `aegiscode/service/api.py`(任务 CRUD、事件、审批决策、取消、审计、凭据状态)。

### 11.1 WebUI 预设演示(Demo Mode)

在 Demo Mode(`AEGIS_DEMO_MODE=1`,公网实例默认开启)下,首页「Start a task」的 **Workspace path 变成预设演示下拉框**(demo1 / demo2 / demo3)。**无需 API Key、无需自己输入任务** —— 选择一个 demo 会**自动填充 Task description**(对应该 demo 的预设),点击 **Start** 即运行该场景并展示运行详情。访问公网地址即可直观体验 AegisCode 三大 Harness 机制:

| 下拉项 | scenario id | 展示的 Harness 机制 |
|---|---|---|
| demo1 · 危险命令拦截 | `dangerous-action-denial` | 治理引擎在工具执行前拒绝 `rm -rf /`;**工具执行次数为 0**,审计记录 DENY + rule_id,Agent 收到 POLICY_DENIED 反馈 |
| demo2 · 失败反馈驱动修复 | `feedback-driven-repair` | 首次实现测试真实失败 → 失败反馈进入下一轮上下文 → Agent 改变动作 → 复验通过,完成由验证器客观复跑判定 |
| demo3 · 高风险操作审批 + 失效 | `approval-binding-invalidation` | 高风险动作暂停等待**真实人工审批**;批准原动作后执行;参数改动后旧审批指纹失效(SUPERSEDED),被篡改的动作**不执行** |

要点:

- **真实机制,零伪造**:三个 Demo 全部真实经过 HarnessCore + MockLLM + 动作解析 + 工具分发 + 治理引擎 + 反馈回灌 + 审批状态机 + 审计哈希链。成功与否来自场景执行器对**真实审计事件流**的确定性断言(与 `make demo` 同一套 `success_conditions`),而非前端硬编码或 HTTP 200。任一失败绝不在前端伪装成功。
- **无 Key、无网络、用 MockLLM**:不访问真实 LLM、不访问外部网络、不操作用户真实仓库。
- **隔离的临时示例工作区**:每次运行有唯一 run ID + 独立临时工作区 + 独立 MockLLM 游标,运行结束后清理(并有惰性清扫兜底);页面刷新后可按 run ID 恢复查询。
- **操作方式**:Demo Mode 下 Workspace path 是下拉框;选 demo1/2/3 → Task description 自动填充 → 点 Start 运行,下方展示状态标签 + 分步时间线 + 审批面板 + 验收摘要 + 重新运行。标准(非 demo)模式仍是自由填写 workspace + task 的原表单。
- **Demo 3 如何审批**:运行到高风险动作时状态变为「等待审批」,面板显示动作摘要与风险,点击「批准原动作」后场景继续;随后场景在指纹绑定后改动参数以演示旧审批失效(与 `make demo` demo3 完全同一 `validate_resume`/SUPERSEDED 机制)。
- **安全边界**:用户只能选择后端白名单中的 Demo ID,不能提交自定义 MockLLM 脚本、任意路径、任意命令、工具白名单或治理策略;Demo 输出经脱敏,不展示密钥/绝对路径/异常堆栈。
- **已知限制**:Render 免费实例休眠后临时数据丢失;Demo 3 需人工点击批准(未做自动播放);单页轮询(非 SSE)。

**`make demo` 与 WebUI Demo 的关系**:两者复用同一份共享场景定义(`aegiscode/demo/scenarios.py`:相同 Demo ID、相同 MockLLM 脚本、相同成功条件)。`make demo` 是命令行评分入口;WebUI Demo 是其图形化、公网可访问的等价实现。一致性由 `tests/demo/test_cli_web_consistency.py` 守护——不存在「前端显示成功而 `make demo` 判定失败」的分叉。Demo API 端点:`GET /demos`(列表)、`POST /demos/{id}/run`(启动,返回 run_id)、`GET /demos/runs/{run_id}`(状态 + 验收);审批复用既有 `GET /tasks/{run_id}/approvals` + `POST /approvals/{id}/decision`。

## 12. 公网部署 URL

**https://aegiscode-o20h.onrender.com**

> 免费实例 15 分钟无请求后休眠，首次访问需等待 ~30s 冷启动。

### 部署架构

```
GitHub main → GitHub Actions CI (make test + make demo + docker build)
  → CI Checks Pass → Render GitHub Integration auto-deploy
  → FastAPI + WebUI (Demo Mode, MockLLM)
```

### Render 配置

- **平台**: Render Web Service (Docker, free plan)
- **Blueprint**: `render.yaml`
- **健康检查**: `GET /healthz` → `{"status":"ok","service":"aegiscode","mode":"demo"}`
- **CI/CD**: GitHub Actions pass → Render auto-deploy (`autoDeployTrigger: checksPass`)

### Demo Mode（公网安全形态）

公网实例以 `AEGIS_DEMO_MODE=1` 运行，提供受限演示沙箱：

- **LLM**: MockLLM（零成本零风险，无需 API Key）
- **工作区**: 仅接受 `"demo"` sentinel，每次任务创建临时副本，任务结束后清理
- **安全限制**: 拒绝任意服务器路径、禁止网络工具、禁止依赖安装、禁止 Git 写操作
- **治理**: 所有治理引擎（路径围栏、命令词法、审批状态机）保持开启
- **持久化**: 临时——Render 免费实例重启/休眠后数据丢失，可重建 Demo 数据
- **冷启动**: 免费实例 15 分钟无请求后休眠，首次访问需等待 ~30s 冷启动

### 部署验证

```bash
make deploy-check DEPLOY_URL=https://<your-render-url>
```

非破坏性检查:`/healthz`、无敏感信息泄漏、WebUI 可访问;当 `/healthz` 报告 `mode=demo` 时,额外校验 `GET /demos` 列出三项预设演示(**不**运行完整 Demo 3,避免消耗时长/改动共享状态)。完整三项 Demo 仍需人工公网验收。

### 本地 Docker 运行（Demo Mode）

```bash
docker build -t aegiscode:render .
docker run --rm -p 8000:8000 \
  -e PORT=8000 \
  -e AEGIS_LLM_PROVIDER=mock \
  -e AEGIS_DEMO_MODE=1 \
  -e AEGIS_HOME=/tmp/aegiscode \
  -e AEGIS_WORKSPACE_ROOT=/tmp \
  -e AEGIS_WORKSPACE_ALLOWED_BASE=/tmp \
  aegiscode:render
# 浏览器打开 http://localhost:8000
# curl http://localhost:8000/healthz
```

## 13. 目录结构

```
aegiscode/            # 核心包
  loop/               # 自实现 HarnessCore 主循环 + 停机判定
  llm/                # LLM 抽象:base / mock / openai_adapter / anthropic_adapter
  protocol/           # 结构化动作协议 + 解析
  governance/         # 命令词法治理 / 路径围栏 / 四档引擎 / 审批 / 分发 / 工厂
  tools/              # 工具注册 + read/write/list/search/run_command/run_tests/finish
  feedback/           # pytest 解析 + 失败分类(回灌)
  memory/             # SQLite 记忆存储 + 6 段上下文装配
  audit/              # 审计事件 + SHA256 哈希链(redact-before-hash)
  security/           # 脱敏器(单一真源正则)
  credentials/        # 分层凭据存储 + 密钥扫描
  persistence/        # sqlite3 open_db(WAL/busy_timeout/FK)+ 手写 SQL 仓储
  config/             # Pydantic schema + YAML/env 加载器
  service/            # ApplicationService + REST API + webui/(静态资源) + 装配
  cli.py              # init/run/serve/config/key/demo
demos/                # 机制演示 + run_demos.py 编排器(make demo 入口)
scripts/              # ci_secret_scan.py(自写确定性密钥闸)
tests/                # 全套自动化测试(与源码目录对应)
docs/                 # SPEC / PLAN / SPEC_PROCESS / AGENT_LOG / REFLECTION / ACCEPTANCE
Dockerfile .dockerignore Makefile pyproject.toml
.gitlab-ci.yml .github/workflows/ci.yml
```

## 14. 安全边界

- **面板无鉴权、仅限本机**:`serve` 默认绑 `127.0.0.1`;`-p` 请只映射 loopback,勿裸暴露公网。
- **工作区隔离**:路径围栏用 `realpath + commonpath`(符号链接安全、前缀碰撞安全)把所有文件动作限制在工作区根内;`run_command` 的路径参数亦过同一围栏。
- **不允许任意绝对路径**:`POST /tasks` 的 `workspace` 经服务端 `allowed_base` 校验,越界(如 `/`、`/etc`)返回 400 且不建任务。
- **命令治理**:默认 allowlist 不含 `cat`/`ls`(通用读取器可读任意路径);解释器族(`python`/`python3`)与紧贴短选项归一化后匹配规则;`DENY` 支配(最严者胜)。
- **凭据**:分层存储、状态仅掩码、redact-before-hash、镜像不烤 Key、异常不泄漏。
- **治理不可为演示关闭**:高风险动作始终经审批,危险动作始终被拒。

## 15. 已知限制

- 单用户 / 单任务 / 单个本地仓库;**锁定 Python + pytest 单栈**(反馈闭环针对 pytest)。
- 记忆为 SQLite 最小实现,**无向量库**(type + project_id + 关键词 LIKE + topK)。
- 本地面板**无鉴权、默认仅绑本机**;公网实例仅以 Demo Mode + MockLLM 运行的受限沙箱形态开放(见第 12 节),不用于真实任务。写快照回滚为 v2,当前为 no-op。
- 密钥扫描器有意限于 `sk-`/`AKIA`/`KEY=` 等已知格式,非通用密钥探测器。
- 真实 Provider 的单次网络调用有 60s 超时;循环有 wall-clock 超时上限。真实模型输出具有非确定性,可能与 MockLLM 的确定性行为不同;真实 LLM 验证为人工触发,不进入 `make test` 与普通 CI。

## 16. 课程要求与追加实现说明

为避免混淆,明确区分三类交付内容的性质:

**课程基础要求(必做,评分核心)**

- 自实现 Agent 主循环(不依赖现成 Agent SDK)、可注入的 LLM 抽象(含 MockLLM 与真实 Provider Adapter)。
- 六个维度(决策 / 工具 / 记忆 / 治理 / 反馈 / 配置)均有最低实现,**治理为重点深化维度**。
- **MockLLM 确定性测试 + 三项机制演示**(`make test` / `make demo`)是评分的核心验证手段,全程零网络、无需真实 LLM 与 API Key。
- Docker 分发 + CI(含名为 `unit-test` 的 job)+ **公网可访问的 demo URL**(SPEC §13.4 / M14「清单第 9 条硬性」)。

**原计划交付项(计划内,首次未完成/暂缓,后续恢复完成)**

- **GitHub Actions CI**:CI 属原计划要求(原始 PLAN 全局约束「CI 必须含名为 `unit-test` 的 job」、SPEC §5.1「Docker + CI」)。首次实施(Task 32)交付了 `.gitlab-ci.yml`;因仓库托管于 GitHub、GitLab pipeline 不会自动执行,后续补齐并硬化了 GitHub Actions workflow(最小权限、并发控制、手动触发、依赖缓存),使 CI 在真实托管平台上运行。这是原计划 CI 要求在实际平台上的完成,非新增 enhancement。
- **Render 公网部署**:属于原始 SPEC 范围(§13.4 / M14 的公网 demo URL 硬性要求)。首次实施阶段未拆分为独立任务而**暂缓**,后续恢复并完成(`render.yaml`、`/healthz`、Demo Mode、安全沙箱、公网 URL、`make deploy-check`)。这不是新增的 enhancement,而是原计划要求的完成。

**迭代修改(对已交付功能的完善,非新能力)**

- **WebUI 预设 MockLLM 演示**:对原 Task 28 已交付 WebUI 的**迭代**——为三项机制增加图形化入口(复用 `make demo` 同一套场景与成功条件),未改变布局、Harness、API、治理、审批或 Demo 逻辑。
- **黑白灰 UI 优化**:纯表现层(CSS)迭代,未改变布局、Harness、API、治理、审批或 Demo 逻辑。

**追加实现(enhancement,课程要求之外)**

- **真实 LLM Provider 可用性完善**:这是本项目**唯一**课程要求之外的追加实现。初始版本已具备可注入 LLM 抽象、MockLLM 与真实 Provider Adapter 框架;后续真实 CLI 测试发现,Adapter 虽在,但系统提示词、动态工具协议、上下文构建与错误反馈不足以让真实模型稳定驱动 Harness。因此新增 enhancement,补齐系统提示词、从 Tool Registry 动态生成的工具协议、Provider 请求组装、CLI 真实模式与人工触发的真实端到端验证(见第 7.1 节)。**课程从未强制要求真实 LLM 端到端测试**,该验证为人工触发,不替代 MockLLM 测试与 `make demo`。

## 17. 持续集成(CI)

本项目有两套 CI,共用**同一测试真相来源**(`Makefile` 的 `make test` / `make demo` + `docker build`),不重复实现测试逻辑:

- **GitLab CI(`.gitlab-ci.yml`)**:课程要求的**主要** CI 配置,签字 PLAN 指定其形态(stages `test`/`security`/`build`,`unit-test` job)。
- **GitHub Actions(`.github/workflows/ci.yml`)**:面向公开 GitHub 仓库的**补充** CI。因本仓库托管于 GitHub,GitLab pipeline 不会自动执行,这套 workflow 才是 GitHub 上真正跑起来的那套。

两者都执行相同的核心自动化验证:

| Job | 命令 | 作用 |
|-----|------|------|
| `unit-test` | `make test` + `make demo` | 全套测试 + 三项确定性机制演示(危险动作拦截 / 失败反馈驱动动作变化 / 审批绑定失效) |
| `secret-scan` | `python scripts/ci_secret_scan.py`(+ gitleaks 兜底) | 自写确定性密钥闸(权威判定)+ gitleaks 兜底(不掩盖主判定) |
| `docker-build` | `docker build -t aegiscode:ci .` | 仅验证镜像可构建,不推送、不需 registry 凭据 |

关键安全属性:`make test` 与 `make demo` **全程 MockLLM 驱动,零网络、不需真实 LLM、不需 API Key、不需任何 Secret**。GitHub Actions 采用最小权限(`permissions: contents: read`),并按分支/PR 分组做并发控制(新推送取消同一 ref 的旧运行)。触发条件:推送到 `main`、针对任意分支的 Pull Request、以及手动 `workflow_dispatch`。

Python 版本在 `pyproject.toml`(`>=3.12`)、Dockerfile(`python:3.12-slim`)、GitLab CI 与 GitHub Actions 之间保持一致(均 3.12)。

> 顶部徽章反映 GitHub Actions 在默认分支 `main` 上的最新运行状态。

## 18. 第三方依赖和许可证

本项目代码尚未附带独立 LICENSE 文件(课程作业)。运行期第三方依赖及其许可证:

| 依赖 | 用途 | 许可证 |
|------|------|--------|
| FastAPI | REST API 框架 | MIT |
| Starlette | FastAPI 底层 ASGI | BSD-3-Clause |
| Uvicorn | ASGI 服务器 | BSD-3-Clause |
| Pydantic | 配置/数据校验 | MIT |
| PyYAML | YAML 配置解析 | MIT |
| keyring | 系统凭据后端 | MIT |
| httpx | HTTP 客户端 | BSD-3-Clause |
| pytest / ruff / mypy(dev) | 测试 / 静态检查 | MIT |

存储层使用 Python 标准库 `sqlite3`(手写 SQL,零 ORM)。以上均为宽松许可证,可安全用于本项目。

