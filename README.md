# AegisCode

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

## 12. 公网部署 URL

**当前未做公网部署**(本轮交付聚焦本地 + Docker 运行与验收)。面板默认**无鉴权、仅限本机**,不适合裸暴露公网。若需公网演示,建议:容器化 + 默认 `AEGIS_LLM_PROVIDER=mock` + 固定/临时工作区 + 端口只绑 loopback 并置于带鉴权的反向代理之后 + **治理机制保持开启**(不得为演示关闭护栏)。届时公网 URL 将回填于此。

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
- WebUI **未公网部署**、无鉴权(仅本机);写快照回滚为 v2,当前为 no-op。
- 密钥扫描器有意限于 `sk-`/`AKIA`/`KEY=` 等已知格式,非通用密钥探测器。
- 真实 provider 的单次网络调用有 60s 超时;循环有 wall-clock 超时上限。

## 16. 第三方依赖和许可证

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

