# AegisCode

[![CI](https://github.com/HELLOI9/AegisCode/actions/workflows/ci.yml/badge.svg)](https://github.com/HELLOI9/AegisCode/actions/workflows/ci.yml)

> 治理优先的编码智能体 Harness：自实现主循环与确定性反馈闭环。
> A policy-governed coding-agent harness with deterministic feedback loops.

## 1. 项目简介

AegisCode 是一个**治理优先的编码智能体框架**（coding-agent harness）。它将 LLM 提议的**每一个动作**送入治理闸门，依次经过命令词法治理、路径围栏和四档风险判定：

* `ALLOW`
* `ALLOW_WITH_AUDIT`
* `REQUIRE_APPROVAL`
* `DENY`

危险动作会在执行前被拦截；高风险动作会暂停并等待人工批准。批准结果与动作指纹绑定，动作参数一旦发生变化，原批准自动失效。

AegisCode 的第二个核心机制是**完整的反馈闭环**：

1. Agent 提议代码或工具动作；
2. Harness 执行动作并运行客观验证；
3. pytest 结果、命令退出码和文件变更范围被标准化；
4. 失败信号回灌至下一轮上下文；
5. Agent 根据客观反馈修正动作；
6. Harness 重新验证并决定任务是否完成。

因此，任务完成状态由 Harness 的客观复验决定，而不是由 LLM 自行宣称。

项目遵循两项核心工程约束：

1. Agent 主循环由本项目自行实现，不依赖现成 Agent SDK；
2. 将真实 LLM 替换为 `MockLLM` 后，治理、反馈、审批、审计和停机机制仍能通过无网络、确定性的自动化测试完成验证。

设计溯源见 `docs/SPEC.md` 与 `docs/SPEC_PROCESS.md`，验收追溯矩阵见 `docs/ACCEPTANCE.md`。

## 2. 目录结构

```text
AegisCode/
├── aegiscode/                # 核心包
│   ├── loop/                 # 自实现 HarnessCore 主循环与停机判定
│   ├── llm/                  # LLM 抽象：base / mock / openai_adapter / anthropic_adapter
│   ├── protocol/             # 结构化动作协议与解析器
│   ├── governance/           # 命令治理 / 路径围栏 / 四档引擎 / 审批 / 分发
│   ├── tools/                # read/write/list/search/run_command/run_tests/finish
│   ├── feedback/             # pytest 解析、失败分类与反馈回灌
│   ├── memory/               # SQLite 记忆存储与六段上下文装配
│   ├── audit/                # 审计事件与 SHA256 哈希链
│   ├── security/             # 脱敏器与安全正则
│   ├── credentials/          # 分层凭据存储与密钥扫描
│   ├── persistence/          # sqlite3 连接与手写 SQL 仓储
│   ├── config/               # Pydantic Schema 与 YAML / env 加载器
│   ├── prompt/               # 系统提示词与动态工具协议
│   ├── service/              # ApplicationService、REST API 与 WebUI
│   ├── demo/                 # CLI 与 WebUI 共享的 Demo 场景
│   └── cli.py                # init / run / serve / config / key / demo
├── demos/                    # 确定性机制演示与 run_demos.py 编排器
├── scripts/                  # 密钥扫描、部署检查、真实 LLM E2E
├── tests/                    # 与源码目录对应的自动化测试
├── docs/                     # SPEC / PLAN / SPEC_PROCESS / AGENT_LOG / REFLECTION / ACCEPTANCE
├── Dockerfile                # python:3.12-slim 镜像
├── Makefile                  # test / demo / deploy-check / e2e-real-llm
├── pyproject.toml            # 包元数据与依赖
├── render.yaml               # Render 部署 Blueprint
├── .gitlab-ci.yml            # GitLab CI
└── .github/workflows/ci.yml  # GitHub Actions CI
```

## 3. 核心架构

```text
LLM 抽象层（OpenAI / Anthropic / MockLLM）
        │
        │ 结构化动作协议（JSON：tool + arguments）
        ▼
自实现 HarnessCore 主循环（loop/harness.py）
        ├─ 动作解析（protocol/parser.py）
        ├─ 治理引擎（governance/）
        │     ├─ 命令词法治理
        │     │     command_lexer + command_rules
        │     │     多条规则同时命中时采用最严格判定
        │     ├─ 路径围栏
        │     │     realpath + commonpath
        │     │     防止符号链接逃逸与路径前缀碰撞
        │     ├─ 四档风险判定
        │     │     engine + factory
        │     ├─ HITL 审批状态机
        │     │     动作指纹绑定 / SUPERSEDED
        │     └─ 工具分发
        │           run_command 的路径参数同样经过路径围栏
        ├─ 反馈闭环
        │     pytest 解析 + 失败分类 → 下一轮上下文
        ├─ 记忆与上下文
        │     SQLite 检索 + 六段预算装配
        ├─ 审计哈希链
        │     脱敏 → SHA256 哈希 → 持久化
        └─ 停机与防死循环
        │    最大步数 / 连续失败 / 无进展 / 超时
        ▼
持久化（sqlite3 + 手写 SQL）
服务层（REST API + WebUI + CLI）
凭据层（keyring → .env → env）
```

治理机制是本项目的主要贡献，详见 `docs/SPEC.md` §11；系统分层和单轮数据流见 §8。

## 4. 测试与机制演示

AegisCode 将确定性自动化测试与机制演示分开：

```bash
make test
make demo
```

其中：

* `make test` 等价于 `pytest -q`，运行完整自动化测试套件；
* `make demo` 运行三项基于 `MockLLM` 的确定性机制演示；
* 两者均不需要网络或 API Key；
* 任一演示契约检查失败时，`make demo` 会以非零退出码结束，可直接作为 CI 门禁。

当前 `main` 分支基线：

```text
make test → 444 passed
make demo → 3 passed, 0 failed
```

逐条需求到测试文件和测试函数的映射见 `docs/ACCEPTANCE.md`。

三项机制演示均由真实 `HarnessCore` 端到端驱动，并通过审计日志、磁盘状态和工具执行计数提供独立证据。

### 4.1 危险动作被治理拦截

`MockLLM` 请求执行危险命令，治理引擎返回 `DENY`：

* 工具执行次数为 `0`；
* 审计日志记录命中的 `rule_id`；
* Agent 收到标准化的 `POLICY_DENIED` 反馈；
* 危险命令不会到达实际执行层。

### 4.2 失败反馈驱动动作改变

Agent 首先提交错误实现，pytest 验证失败。失败结果被标准化并回灌至下一轮上下文，Agent 随后提交不同的修正动作。

任务完成状态由 Harness 重新运行 pytest 后确定，而不是依据 Agent 的自然语言声明。

### 4.3 审批绑定与动作失效

高风险动作触发 `REQUIRE_APPROVAL` 并暂停执行：

* 批准原始动作后，动作可以继续执行；
* 动作参数被修改后，动作指纹发生变化；
* 原审批状态转为 `SUPERSEDED`；
* 被篡改的动作不会执行，必须重新经过治理和审批。

此外，CLI 提供：

```bash
aegiscode demo
```

该命令随 Python 包和 Docker 镜像一同发布，可直接运行 `docs/SPEC.md` §16.4 中定义的四项演示，其中包括路径围栏的符号链接逃逸测试。

## 5. 本地运行与 LLM 接入

AegisCode 通过统一的 `LLMClient` 接口接入以下三类 Provider：

* `MockLLM`
* `OpenAIAdapter`
* `AnthropicAdapter`

LLM Provider 只负责消息传输和响应标准化，不负责维护 Agent Loop、执行工具或制定治理策略。主循环、治理、反馈、审计和停机逻辑均由 AegisCode 自身实现。

### 5.1 环境安装

AegisCode 要求：

```text
Python >= 3.12
```

创建虚拟环境并安装项目：

```bash
python -m venv .venv
source .venv/bin/activate

# Windows PowerShell：
# .venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

仅安装运行期依赖时，可执行：

```bash
pip install -e .
```

运行期依赖包括：

* FastAPI
* Uvicorn
* Pydantic
* PyYAML
* keyring
* httpx

持久化层仅使用 Python 标准库 `sqlite3`。

### 5.2 初始化

生成默认配置文件：

```bash
aegiscode init
```

该命令会在当前目录生成 `aegis.yaml`。即使不生成配置文件，AegisCode 也会使用内置的安全默认值。

查看当前配置摘要：

```bash
aegiscode config
```

启动本地 WebUI：

```bash
aegiscode serve --host 127.0.0.1 --port 8000
```

然后在浏览器中打开：

```text
http://127.0.0.1:8000
```

### 5.3 Provider 配置

Provider 可通过 `aegis.yaml` 配置：

```yaml
llm:
  provider: openai        # openai | anthropic | mock
  model: gpt-4o
  base_url: null
```

也可以通过环境变量覆盖：

```bash
export AEGIS_LLM_PROVIDER=openai
export AEGIS_LLM_MODEL=gpt-4o
```

#### OpenAI 及兼容端点

`OpenAIAdapter` 会向以下端点发送请求：

```text
{base_url}/chat/completions
```

因此，DeepSeek、通义、vLLM 或其他 OpenAI 兼容服务可以直接填写其 API Base：

```yaml
llm:
  provider: openai
  model: deepseek-chat
  base_url: https://api.deepseek.com
```

本地运行的 vLLM 等兼容服务也可使用相同方式接入：

```yaml
llm:
  provider: openai
  model: your-local-model
  base_url: http://127.0.0.1:8001/v1
```

具体 `base_url` 是否需要包含 `/v1`，取决于目标服务暴露的兼容接口路径。

#### Anthropic 端点

`AnthropicAdapter` 会向以下端点发送请求：

```text
{base_url}/v1/messages
```

默认 API Base 为：

```text
https://api.anthropic.com
```

示例配置：

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-5
  base_url: https://api.anthropic.com
```

各 Provider 的角色映射、system message 处理方式、响应字段、认证错误和限流错误均封装在对应适配器中，主循环与治理层不感知具体模型厂商。

### 5.4 Prompt 与工具协议

真实模型能够驱动 Harness，依赖于 `aegiscode/prompt/` 中与 Provider 无关的 `PromptBuilder`。

`PromptBuilder` 根据配置和工具注册表构造完整的 system prompt，其中包括：

* Agent 身份和任务目标；
* 工作区边界；
* 每轮只允许提交一个结构化动作；
* pytest 客观通过前禁止调用 `finish`；
* 测试通过后立即结束，禁止重复成功动作；
* 当前允许使用的工具及其参数协议。

工具协议从 `ToolRegistry` 动态生成。被配置禁用或未注册的工具不会出现在 system prompt 中，从结构上避免模型调用不可用工具。

`make test` 始终使用确定性测试替身，不会选择真实 Provider。即使当前环境配置了 API Key，普通测试也不会触发网络请求。

### 5.5 API Key 安全

API Key 按以下优先级解析：

```text
keyring → .env（需要显式开启）→ 环境变量
```

凭据不会被硬编码、提交到仓库或写入审计日志。

推荐使用 CLI 安全管理 Key：

```bash
aegiscode key set
aegiscode key status
aegiscode key clear
```

其中：

* `key set` 使用 `getpass` 录入，不回显且不进入 Shell 历史；
* `key status` 只显示掩码，例如“前 3 位 + … + 后 4 位”；
* `key clear` 删除已保存的凭据；
* 选择真实 Provider 但未配置 Key 时，程序会安全拒绝，不会发送网络请求。

审计日志在计算 SHA256 和写入数据库之前先执行脱敏。脱敏规则覆盖：

* `sk-...`
* `sk-ant-...`
* AWS `AKIA...`
* `KEY="..."`
* 其他已定义的常见凭据格式

完整凭据威胁模型见 `docs/SPEC.md` §12。

### 5.6 使用真实 LLM 运行任务

首先选择真实 Provider，并配置 API Key：

```bash
source .venv/bin/activate

export AEGIS_LLM_PROVIDER=openai
export AEGIS_LLM_MODEL=gpt-4o

aegiscode key set
```

然后创建工作区并提交任务：

```bash
mkdir -p ./sandbox

aegiscode run \
  --workspace ./sandbox \
  --task "创建 src/strutil.py，实现 reverse(s) 返回字符串反转；同时创建 tests/test_strutil.py，使用 pytest 断言 reverse('abc') == 'cba' 且 reverse('') == ''。pytest 通过后再调用 finish。" \
  --watch
```

`--task` 后的内容就是提交给 Agent 的任务描述。

`--watch` 会在任务结束后输出逐步事件流，包括：

* 每轮结构化动作；
* 治理判定；
* 工具执行结果；
* 标准化反馈；
* 审批状态；
* 最终停机原因。

使用真实 LLM 时必须注意以下两点。

#### 第一，任务完成由 pytest 客观复跑决定

AegisCode 不接受 LLM 自称“任务已完成”作为完成依据。

任务通常需要 Agent 同时创建：

* 业务实现；
* 对应的 pytest 测试。

如果工作区中不存在可成功运行的测试，最终验证器会持续拒绝 `finish`。Agent 可能因此空转，最终以以下原因之一停止：

* `NO_PROGRESS`
* `MAX_STEPS`
* 连续失败限制
* wall-clock 超时

#### 第二，写入路径必须符合路径策略

默认写白名单目录为：

```text
src/
tests/
```

写入工作区根目录通常会被判定为：

```text
REQUIRE_APPROVAL
```

`aegiscode run` 是同步的一次性 CLI 命令，不提供交互式审批入口。在 fail-safe 策略下，无法完成审批的高风险动作会被拒绝。

需要处理人工审批时，应使用 WebUI：

```bash
aegiscode serve --host 127.0.0.1 --port 8000
```

### 5.7 真实 LLM 端到端验证

项目提供：

```bash
make e2e-real-llm
```

该命令使用真实 Provider 运行一个内置固定任务：

1. 创建临时工作区；
2. 让真实模型创建实现与测试；
3. 运行完整治理流程；
4. 在 pytest 全部通过后完成任务。

该命令用于人工验证真实模型能否驱动完整 Harness，不属于普通自动化测试：

* 需要真实 API Key；
* 需要网络连接；
* 可能产生 API 费用；
* 不包含在 `make test` 中；
* 不进入普通 CI 流程。

### 5.8 Docker 运行

Docker 镜像基于：

```text
python:3.12-slim
```

`.dockerignore` 会排除：

```text
.env
*.pem
*.key
*.db
tests/
docs/
```

凭据必须在容器运行时注入，不会写入镜像。

构建镜像：

```bash
docker build -t aegiscode .
```

使用 `MockLLM` 启动：

```bash
docker run --rm \
  -e AEGIS_LLM_PROVIDER=mock \
  -p 127.0.0.1:8000:8000 \
  aegiscode
```

接入真实 OpenAI Provider：

```bash
docker run --rm \
  -e AEGIS_LLM_PROVIDER=openai \
  -e OPENAI_API_KEY=sk-... \
  -v "$PWD/sandbox":/workspace \
  -p 127.0.0.1:8000:8000 \
  aegiscode
```

WebUI 当前不提供身份认证。除受限 Demo Mode 外，请仅将端口绑定到 `127.0.0.1`，不要直接暴露到公网。

## 6. WebUI 与公网部署

本地启动 WebUI：

```bash
aegiscode serve --host 127.0.0.1 --port 8000
```

WebUI 提供以下功能：

* 提交任务；
* 查看任务状态；
* 查看逐步事件流；
* 审批或拒绝待审批动作；
* 查看凭据状态；
* 运行内置 Demo。

所有动态内容均通过 `textContent` 渲染，避免将任务文本直接作为 HTML 注入页面。REST API 定义见：

```text
aegiscode/service/api.py
```

公网演示实例：

```text
https://aegiscode-o20h.onrender.com
```

Render 免费实例在 15 分钟无请求后会进入休眠，首次访问可能需要约 30 秒完成冷启动。

部署流程如下：

```text
GitHub main
  → GitHub Actions CI
      make test
      make demo
      docker build
  → Checks Pass
  → Render auto-deploy
      autoDeployTrigger: checksPass
  → FastAPI + WebUI
      Demo Mode + MockLLM
```

公网实例以以下配置运行：

```text
AEGIS_DEMO_MODE=1
```

Demo Mode 使用受限演示沙箱：

* LLM 固定为 `MockLLM`；
* 不需要 API Key；
* 不产生模型调用费用；
* 工作区只接受 `"demo"` sentinel；
* 每次任务创建独立临时副本；
* 任务结束后自动清理；
* 拒绝任意服务器路径；
* 禁止网络工具与依赖安装；
* 治理引擎、路径围栏和审计机制保持开启。

Demo Mode 下，首页的 Workspace path 输入框会变为场景选择框：

```text
demo1
demo2
demo3
```

选择场景后，页面会自动填充对应任务描述，点击 Start 即可运行。

Web Demo 与 `make demo` 复用同一份场景定义：

```text
aegiscode/demo/scenarios.py
```

CLI 与 WebUI 的场景一致性由以下测试守护：

```text
tests/demo/test_cli_web_consistency.py
```

健康检查接口：

```http
GET /healthz
```

返回：

```json
{
  "status": "ok",
  "service": "aegiscode",
  "mode": "demo"
}
```

可以运行以下命令执行非破坏性部署验证：

```bash
make deploy-check DEPLOY_URL=https://aegiscode-o20h.onrender.com
```

## 7. 安全边界

### 7.1 WebUI 边界

普通 WebUI 当前没有身份认证，默认仅绑定：

```text
127.0.0.1
```

除受限 Demo Mode 外，不应将普通 WebUI 直接暴露到公网。

Docker 端口映射也应限制为：

```bash
-p 127.0.0.1:8000:8000
```

### 7.2 工作区隔离

路径围栏使用：

```text
realpath + commonpath
```

它会将文件操作限制在工作区根目录内，并防止：

* `../` 路径穿越；
* 绝对路径逃逸；
* 符号链接逃逸；
* 相同路径前缀导致的错误判定。

`run_command` 中涉及的路径参数同样经过路径围栏检查。

### 7.3 服务端工作区限制

`POST /tasks` 接收的 `workspace` 会经过服务端 `allowed_base` 校验。

当路径越界时：

* 服务端返回 HTTP 400；
* 不创建任务；
* 不进入 Agent Loop；
* 不执行任何工具。

### 7.4 命令治理

默认命令 allowlist 不包含 `cat` 和 `ls`。

命令进入治理引擎后会经过：

* Shell 词法解析；
* 解释器族识别；
* 紧贴短选项归一化；
* 多规则匹配；
* 最严格结果优先。

当多条规则同时命中时，`DENY` 具有最高优先级。

执行层使用：

```text
shell=False
argv 数组
cwd 固定为工作区
```

从而避免将未经控制的字符串直接交给 Shell 解释执行。

### 7.5 凭据与审计

AegisCode 对凭据采取以下保护：

* 分层凭据存储；
* 状态接口只返回掩码；
* 日志采用 redact-before-hash；
* Docker 镜像不包含 API Key；
* 异常信息不得泄漏明文凭据；
* 密钥扫描器在 CI 中检查常见格式。

### 7.6 治理不可因演示关闭

Demo Mode 只限制工作区和工具能力，不关闭治理机制：

* 高风险动作仍需审批；
* 危险动作仍被拒绝；
* 文件动作仍受路径围栏约束；
* 所有动作仍写入审计链。

## 8. 已知限制

* 当前面向单用户、单任务和单个本地仓库；
* 仅支持 Python 与 pytest 技术栈；
* 记忆系统为 SQLite 最小实现，不使用向量数据库；
* 记忆检索采用 `type + project_id + 关键词 LIKE + topK`；
* 密钥扫描器仅覆盖 `sk-`、`AKIA`、`KEY=` 等已知格式，不是通用秘密检测器；
* 写操作快照回滚预留为后续版本，当前实现为 no-op；
* 当前只支持 Linux 路径语义，不处理 Windows 文件系统的大小写折叠；
* 真实模型输出具有非确定性，行为可能与 `MockLLM` 不同；
* 单次网络调用默认超时为 60 秒；
* Agent Loop 受最大步数、连续失败、无进展和 wall-clock 上限约束。

## 9. 依赖与许可证

本项目为课程作业，目前未附带独立的 `LICENSE` 文件。

主要运行期和开发期依赖如下：

| 依赖        | 用途              | 许可证          |
| --------- | --------------- | ------------ |
| FastAPI   | REST API 框架     | MIT          |
| Starlette | FastAPI 底层 ASGI | BSD-3-Clause |
| Uvicorn   | ASGI 服务器        | BSD-3-Clause |
| Pydantic  | 配置与数据校验         | MIT          |
| PyYAML    | YAML 配置解析       | MIT          |
| keyring   | 系统凭据后端          | MIT          |
| httpx     | HTTP 客户端        | BSD-3-Clause |
| pytest    | 自动化测试           | MIT          |
| Ruff      | 静态检查            | MIT          |
| mypy      | 类型检查            | MIT          |

持久化层使用 Python 标准库 `sqlite3`，通过手写 SQL 实现，不依赖 ORM。
