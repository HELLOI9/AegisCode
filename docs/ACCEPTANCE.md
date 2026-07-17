# AegisCode — 验收追溯矩阵 (ACCEPTANCE)

本文件把课程验收清单(见 `docs/SPEC.md` §15 与 acceptance spec §十)的每条要求映射到**可定位的真实证据**:实现文件、自动化测试(文件 + 函数名)、演示/证据命令、状态。每个单元格都是可 grep / 可复跑的引用,而非「已完成」空话。基线数据(当前 worktree `webui-mock-demos`,追加任务 C 完成后,root venv 复跑):`make test` → **419 passed, 1 warning**;`make demo`(`python -m demos.run_demos`)→ **3 passed, 0 failed (exit 0)**。(历史基线:`m8-hardening` 曾为 325 passed;追加任务 B Render 部署后 344;追加任务 C 加 75 个演示测试 → 419。下方部分早期行内引用的 325 为当时任务验证时的历史计数,未回改。)

---

## 追溯矩阵

| 要求 | 实现位置 | 自动测试 | 演示/证据 | 状态 |
|---|---|---|---|---|
| 自实现 Agent Loop(无 SDK) | `aegiscode/loop/harness.py`(`class HarnessCore`,`run()` 单动作 while 循环,模块 docstring 标 "self-written while-loop";装配见 `aegiscode/service/assembly.py`) | `tests/loop/test_harness.py`(`test_demo1_dangerous_command_denied` / `test_demo2_failure_feedback_changes_action` / `test_finish_rejected_continues_to_max_steps`) | `make demo`(全程走真实 HarnessCore);AGENT_LOG line 344 记录 grep langchain/autogen/crewai 皆无 | ✅ 通过 |
| MockLLM(离线确定性) | `aegiscode/llm/mock.py`(`class MockLLM(LLMClient)`,按序响应队列 + 记录 messages;零网络零 key) | `tests/llm/test_mock.py`;接口一致性 `tests/llm/test_adapters.py` | `make demo` 三个演示全部 MockLLM 驱动、零网络;CI `make demo` 无 API key | ✅ 通过 |
| 危险动作拦截(DENY) | `aegiscode/governance/command_rules.py`(`judge_command`,5 层管线)+ `command_lexer.py` + `engine.py` | `tests/governance/test_command_rules.py`(`test_rm_denied_by_metastructure_or_allowlist` / `test_python_dash_c_denied` / `test_pipe_denied`)、`test_command_bypass.py`(`test_c1_python3_dash_m_denied` 等旁路加固) | Demo 1 `demos/demo1_dangerous_denied.py`(`rm -rf /` → DENY,tool 执行次数=0,审计 GOVERNANCE_DECISION=DENY 带 rule_id) | ✅ 通过 |
| 失败反馈回灌 | `aegiscode/loop/harness.py`(反馈写入下一轮 `last_feedback`/上下文)+ `aegiscode/feedback/classifier.py`(`classify`,`TEST_FAILURE` 等 8 类)+ `pytest_parser.py` | `tests/feedback/test_classifier.py`(`test_classify_test_failure` / `test_summarize_pytest_keeps_failed_names`)、`tests/loop/test_harness.py::test_demo2_failure_feedback_changes_action` | Demo 2 `demos/demo2_feedback_loop.py`(失败反馈进入下一轮 MockLLM messages,轮3 动作≠轮1,COMPLETED 由最终验证复跑判定) | ✅ 通过 |
| 审批绑定与失效(HITL) | `aegiscode/governance/approval.py`(`fingerprint`、`validate_resume`、`ApprovalState.SUPERSEDED`、`remember`/`check_remembered`) | `tests/governance/test_approval_binding.py`(`test_execute_approved_same_fingerprint_runs` / `test_execute_approved_changed_fingerprint_superseded`)、`tests/loop/test_approval_binding.py`、`tests/governance/test_approval.py` | Demo 3 `demos/demo3_approval_binding.py`(暂停时 0 执行 → 批准执行原始快照 → 改指纹 SUPERSEDED 不执行 → 审计全流程) | ✅ 通过 |
| 统一测试命令 | `Makefile`(`test:` → `pytest -q`) | 全套 `tests/`(325 passed) | `make test` → 325 passed | ✅ 通过 |
| 统一演示命令 | `Makefile`(`demo:` → `python -m demos.run_demos`)+ `demos/run_demos.py` | `tests/demos/test_run_demos.py`、`tests/demos/test_demos.py`、`tests/demos/test_demo3_approval_binding.py` | `make demo` → "AegisCode mechanism demos: 3 passed, 0 failed" | ✅ 通过 |
| 凭据安全(生命周期) | `aegiscode/credentials/store.py`(`CredentialStore` keyring→.env→env,`status` 只返 configured+masked,fail-safe)+ `backend.py`(os.open 0o600)+ `scanner.py`(自写扫描器) | `tests/credentials/test_store.py`(`test_status_masks_never_plaintext` / `test_dotenv_disabled_by_default` / `test_env_fallback`)、`test_scanner.py`(`test_detects_planted_key`)、`test_backend_perms.py` | CLI `aegiscode key set/status/clear`;`scripts/ci_secret_scan.py`(CI security stage);容器内 `/credentials/status`=`{"configured":false,"masked":null}`(AGENT_LOG line 441) | ✅ 通过 |
| Docker 分发 | `Dockerfile`(python:3.12-slim,editable install,`CMD ["aegiscode","serve","--host","0.0.0.0","--port","8000"]`,key 绝不入镜像)+ `.dockerignore` | `tests/test_docker_build.py`(`test_dockerfile_has_no_key_and_runtime_cmd` / `test_dockerfile_copies_no_secrets` / `test_dockerignore_excludes_secrets_and_cruft`) | `docker build -t aegiscode .`(CI docker-build stage);AGENT_LOG line 439 记录 `docker build -t aegiscode:m8 .` 成功 + `docker run` clean exit 0 | ✅ 通过 |
| WebUI | `aegiscode/service/webui/{index.html,app.js,style.css}`(原生,无框架)+ `aegiscode/service/api.py`(FileResponse 路由 + 8 JSON 端点) | `tests/service/test_webui_served.py`(`test_root_serves_html` / `test_app_js_served_with_polling_logic` / `test_app_js_renders_changed_files_diff`)、`tests/service/test_api.py` | `aegiscode serve` + Docker run + 公网 https://aegiscode-o20h.onrender.com/ | ✅ 通过 |
| GitLab CI(`unit-test` job) | `.gitlab-ci.yml`(stages test/security/build;`unit-test` job 跑 `make test` + `make demo`)+ 镜像 `.github/workflows/ci.yml`(GitHub 实际执行) | `tests/test_ci_config.py`(`test_gitlab_ci_has_unit_test_job_running_make_test` / `test_github_actions_mirror_exists_and_runs_make_test` / `test_gitlab_ci_has_security_and_build_jobs`) | `.gitlab-ci.yml` `unit-test` job(未 `\|\| true` 兜底,demo 失败即 fail);secret-scan + docker-build 两 stage | ✅ 通过 |
| GitHub Actions(补充 CI) | `.github/workflows/ci.yml`(三 job:`unit-test`/`secret-scan`/`docker-build`;`on: push[main]`+`pull_request`+`workflow_dispatch`;`permissions: contents: read`;concurrency 按 ref 分组;setup-python 3.12 + pip 缓存) | `tests/test_ci_config.py::test_github_actions_mirror_exists_and_runs_make_test` | `make test`(325 passed)、`make demo`(3 passed/0 failed, exit 0)、`docker build -t aegiscode:ci .`;MockLLM 零网络无 API Key。**GitHub Actions 远端运行成功**([run 29395515280](https://github.com/HELLOI9/AegisCode/actions/runs/29395515280),commit `7813f79`,三 job 全绿:unit-test/secret-scan/docker-build;初次绿色运行 29395362746@`bd98d9c`),PR [#10](https://github.com/HELLOI9/AegisCode/pull/10) | ✅ 通过 |
| Render 公网部署 | `render.yaml`(Web Service, Docker, free, /healthz, checksPass) | `tests/test_deploy_check.py`(9 tests) + `tests/service/test_healthz.py`(3 tests) + `tests/service/test_demo_mode.py`(7 tests) | `make deploy-check DEPLOY_URL=https://aegiscode-o20h.onrender.com` → All checks passed | ✅ 通过 |
| 健康检查 | `aegiscode/service/api.py::healthz`(`GET /healthz` → `{"status":"ok","service":"aegiscode","mode":"..."}`) | `tests/service/test_healthz.py`(`test_healthz_returns_200` / `test_healthz_does_not_leak_secrets` / `test_healthz_has_mode_field`) | 公网 `https://aegiscode-o20h.onrender.com/healthz` = 200 | ✅ 通过 |
| Demo Mode | `aegiscode/service/demo_mode.py` + `api.py` 集成 + WebUI `app.js` 前端适配 | `tests/service/test_demo_mode.py`(7 tests: 路径拒绝、demo sentinel、临时工作区创建/清理、/healthz mode 报告) | Docker 容器 Demo Mode: 任意路径 400, demo workspace 创建成功, /ui-config=true | ✅ 通过 |
| 部署验证命令 | `Makefile::deploy-check` + `scripts/deploy_check.py` | `tests/test_deploy_check.py`(9 tests: healthz/secrets/webui/main 逻辑) | `make deploy-check DEPLOY_URL=https://aegiscode-o20h.onrender.com` → exit 0 | ✅ 通过 |
| CI/CD 联动 | GitHub Actions CI + Render GitHub Integration (checksPass) | CI pass → Render auto-deploy | Render Service 已连接, PR #11 合并后自动部署成功 | ✅ 通过 |

### WebUI 预设 MockLLM 演示(追加任务 C)

三个 Demo 复用共享场景层 `aegiscode/demo/scenarios.py`(唯一真相源:相同 id/`mock_script`/`success_conditions`),经 `DemoRunManager`(`aegiscode/demo/service.py`)真实驱动 HarnessCore + MockLLM + 治理 + 反馈 + 审批状态机 + 审计;Demo API 见 `aegiscode/service/api.py`(`GET /demos` / `POST /demos/{id}/run` / `GET /demos/runs/{id}`,审批复用既有 `/approvals/{id}/decision`)。本地基线:`make test` → **419 passed**;`make demo` → **3 passed, 0 failed**。

| 要求 | 实现位置 | 自动测试 | 公网证据 | 状态 |
|---|---|---|---|---|
| Web Demo 列表 | `scenarios.REGISTRY` + `api.py` `GET /demos` | `tests/service/test_demo_api.py::test_list_demos_returns_three_scenarios` | 公网 Workspace-path 下拉列 demo1/2/3;`/demos`=200 | ✅ 通过(公网人工验收 2026-07-16) |
| 危险动作演示 | 共享场景 `dangerous-action-denial` | `tests/demo/test_scenarios.py`、`test_run_manager.py::test_denial_run_zero_exec_and_deny`、`demos/demo1_dangerous_denied.py` | Web Demo 1(DENY,0 执行);公网人工验收通过 | ✅ 通过(公网人工验收 2026-07-16) |
| 反馈修正演示 | 共享场景 `feedback-driven-repair` | `test_run_manager.py::test_feedback_run_completes`、`demos/demo2_feedback_loop.py` | Web Demo 2(TEST_FAILURE→修复→COMPLETED);公网人工验收通过 | ✅ 通过(公网人工验收 2026-07-16) |
| 审批失效演示 | 共享场景 `approval-binding-invalidation` + `dispatcher.execute_approved`/`approval.validate_resume` | `test_demo_api.py::test_demo3_interactive_approval_flow_over_http`、`test_run_manager.py` | Web Demo 3(真实人工审批 + SUPERSEDED);公网人工验收通过 | ✅ 通过(公网人工验收 2026-07-16) |
| MockLLM 公网运行 | `render.yaml`(`AEGIS_LLM_PROVIDER=mock`)+ `DemoRunManager` 每 run 新建 `MockLLM(script)` | `test_run_manager.py::test_isolation`(游标不共享)、离线全套 | 无 Key 演示;公网 `/healthz` mode=demo,人工验收通过 | ✅ 通过(公网人工验收 2026-07-16) |
| Demo 工作区隔离 | `DemoRunManager`(`mkdtemp` under allowed_base + 终态清理 + `_sweep_orphaned_runs`) | `test_run_manager.py::test_isolation` / `test_cleanup` / 惰性清扫测试 | 本地 Docker 事件无 `/tmp` 路径泄漏 | ✅ 通过(本地) |
| CLI/Web 一致性 | 场景执行器 `scenarios.py`(共享脚本 + 成功条件) | `tests/demo/test_cli_web_consistency.py`(id 映射 / 同脚本 / 同成功条件 / CLI 契约↔Web 验收同 run / `_CHECK_PY` pin) | `make demo` + WebUI 同源;无「前端成功而 make demo 失败」分叉 | ✅ 通过 |

> 说明:七行**全部 ✅ 通过**。实现 + 自动测试 + 本地 Docker Demo Mode 实测(见 AGENT_LOG「Docker 验证」)+ **公网人工验收(2026-07-16,PR #12 squash-merge `fb7029f` → Render 重部署 https://aegiscode-o20h.onrender.com)** 均已通过:公网 `/healthz` mode=demo、`/ui-config` demo_mode=true、`/demos`=200,Workspace-path 下拉可选 demo1/2/3、选中自动填充 task description、三项 Demo 人工点击(含 Demo 3 审批交互)均正常,未发现问题。CLI/Web 一致性与工作区隔离由自动测试 + 本地验证确证。

### 其他 SPEC 支柱(追加追溯)

| 要求 | 实现位置 | 自动测试 | 演示/证据 | 状态 |
|---|---|---|---|---|
| 路径围栏(乙) | `aegiscode/governance/path_fence.py`(realpath 归属判定 + 敏感文件黑名单 + 新建文件父目录判定) | `tests/governance/test_path_fence.py`(`test_symlink_escape_denied` / `test_parent_traversal_denied` / `test_sensitive_file_denied` / `test_sibling_prefix_dir_denied`)、`test_fence_ctx_root.py` | `demos/demo3_symlink_escape.py`(软链 `evil→/etc/passwd` → DENY);b48f4a9 修 realpath 后再查敏感模式(符号链接旁路) | ✅ 通过 |
| 命令治理(甲) | `aegiscode/governance/command_lexer.py`(shlex + 结构安全层)+ `command_rules.py`(允许列表 + 危险参数,most-restrictive-wins)+ `dispatcher.py`(执行层 shell=False) | `tests/governance/test_command_lexer.py`、`test_command_rules.py`(`test_pip_install_requires_approval` / `test_not_in_allowlist_denied`)、`test_command_bypass.py`、`test_run_command_fence.py`、`tests/tools/test_command_tool.py` | Demo 1;`run_command` 执行层 `shell=False` + argv 数组 + cwd 锁工作区 | ✅ 通过 |
| 审计哈希链 | `aegiscode/audit/chain.py`(`append` SHA256(prev‖body)、`verify_chain(task_id, expected_count)`、写前 redact)+ `events.py` | `tests/audit/test_chain.py`(`test_tamper_detected` / `test_tamper_row_deletion_detected` / `test_tail_truncation_detected_with_expected_count` / `test_payload_redacted`) | Demo 1/3 断言审计事件;WebUI verify-chain 显示 `chain_valid` | ✅ 通过 |
| 停机 / 防死循环 / 超时 | `aegiscode/loop/termination.py`(`TerminationReason` 10 种含 `TIMEOUT` + `LoopCounters` 优先级,wall-clock 超时最先判定)+ `harness.py`(`time.monotonic` 注入 elapsed)+ `dispatcher.py`(command_timeout)+ adapter `urlopen(timeout=)` | `tests/loop/test_termination.py`(`test_max_steps` / `test_consecutive_failures` / `test_no_progress` / `test_priority_invalid_action_wins_over_max_steps`)、`tests/loop/test_timeout.py` | `test_finish_rejected_continues_to_max_steps`(finish 未过验证 → 撞上限转 MAX_STEPS) | ✅ 通过 |
| 记忆存取 | `aegiscode/memory/store.py`(写入过脱敏、type+project+关键词 LIKE+topK 检索)+ `context_builder.py`(6 段预算装配) | `tests/memory/test_store.py`(`test_refuses_secret_value` / `test_write_and_retrieve_by_keyword` / `test_agent_memory_not_governance_usable` / `test_retrieve_is_project_scoped`)、`tests/loop/test_memory_integration.py`(`test_retrieval_reaches_context`) | M8 接入主循环(AGENT_LOG line 416:`build_context` 由 `memories=[]` 硬编码改为真实检索接入) | ✅ 通过 |
| 配置(YAML + env 覆盖) | `aegiscode/config/schema.py`(Pydantic `extra="forbid"`,secure-by-default 内置规则)+ `loader.py`(`load_config`,仅 `AEGIS_LLM_PROVIDER`/`AEGIS_LLM_MODEL` 两项 env 覆盖,`ConfigError`) | `tests/config/test_loader.py`(`test_unknown_top_level_field_raises` / `test_bad_decision_tier_raises` / `test_command_rules_flat_shape` / `test_env_overrides_provider_and_model` / `test_default_command_rules_pip_install_require_approval`) | 出厂 `aegis.yaml`;零配置(无 YAML)危险规则仍生效(`test_command_rules.py::test_default_command_rules_*`,SPEC §M11 secure-by-default) | ✅ 通过 |

---

## PLAN.md 完整性检查

- `grep -cE "Task [0-9]+" docs/PLAN.md` = 43 处提及(含引用性文字);**任务标题** `### Task N:` 共 32 个。
- `grep -c "✅ DONE" docs/PLAN.md` = **32**。
- 匹配 `^### Task [0-9]+:.*✅ DONE \(` 的标题 = **32**;grep 「有 Task 标题但缺 `✅ DONE (`」结果为**空**。
- 结论:**32 个 task 全部 `✅ DONE` 且每个都带 commit hash**(例:Task 1 `c6f8f28`,Task 17 `93d1ca7`,Task 19 `af405cf,+8c36acb,+7f1477d`,Task 32 `3698399,+966e95d`)。多数 task 附有 fix/review 追加 hash(`+xxxxxxx`),表明经评审迭代。**未发现「代码已做但未勾选」的异常**。

## SPEC_PROCESS.md 完整性检查

未修改该文件,仅核验五要素齐全(行号 = 章节标题所在行):

- **(a) ≥3 轮 brainstorming / 关键迭代**:第 1–25 轮完整逐轮记录(line 25 起,至 line 449「第 24 轮」/ line 465「第 25 轮」);综合回顾 line 467;§四「至少三轮实质性修改(我推翻/修正 Claude 的节点)」line 508。**齐全**。
- **(b) 冷启动(冷启动)章节 + 结论**:line 534「冷启动验证(§4.5):陌生智能体试运行与规约修订」,含 §一验证设置(541)、§二暴露的缺陷(548)、§四验证结论(587)。共**五轮**冷启动(line 534/595/642/676/733)。**齐全**。
- **(c) 冷启动后的 SPEC/PLAN 修订**:line 564「§三 修订(含前后 diff 要点)」;第二轮 line 622「三、修订(本轮)」;第四轮 line 702「三、修订(方向 A:把规则烤进代码默认,secure-by-default)」。**齐全**。
- **(d) 实现期暴露的规约问题**:line 548「二、暴露的缺陷(按严重度)」;第四轮 line 688「二、本轮挖出的真实缺陷(前三轮全未发现)」(fail-open 安全缺陷 D-CS15,对应 commit b48f4a9 / secure-by-default 修复)。**齐全**。
- **(e) 关键设计调整 + 人工决策**:line 508「§四 至少三轮实质性修改(我推翻/修正 Claude 的节点)」;SPEC 附录 A 亦记三处用户推翻(绝对路径第13轮 / Agent 写记忆第16轮 / 云部署鉴权第19轮);流程教训 line 651「教训 5」。**齐全**。

结论:SPEC_PROCESS.md 五要素**全部present**,无需补写。

---

## 追加任务 D：真实 LLM Provider 可用性（Enhancement，课程要求之外）

> **定位声明：** 此为课程要求之外的追加验收。课程评分口径（§A.4C）只要求 MockLLM 确定性单测；真实 LLM 端到端不是课程强制要求。

### 真实 LLM 端到端测试（人工触发，2026-07-17）

| 验收项 | 证据 |
|---|---|
| 使用了真实 Provider（非 MockLLM） | `real_provider: PASS`；`provider=openai model=deepseek-chat`（DeepSeek OpenAI 兼容端点） |
| `add.py` 由 Harness 工具创建 | `add_py_exists: PASS`；`write_file_tool_executed_events=2` |
| `test_add.py` 由 Harness 工具创建 | `test_add_py_exists: PASS`；`write_file_tool_executed_events=2` |
| 动作经解析→治理→工具分发 | `governance_decision_events=3`；审计流记录每次 ACTION_PROPOSED→GOVERNANCE_DECISION→TOOL_EXECUTED |
| HITL 审批路径演示 | `approval_approved=True`；`write_file` 到工作区根触发 REQUIRE_APPROVAL → 自动批准 → 执行 |
| pytest 结果进入 Harness 且 COMPLETED 依赖 pytest 通过 | `completed: PASS`；`pytest_passed: PASS`；Harness 最终验证器独立复跑 pytest 通过后方 COMPLETED |
| 工作区外无副作用 | 生成文件仅 `add.py`/`test_add.py`/`__pycache__`，无跨目录写入 |
| 日志无 Secret | 输出仅含 `provider/model/configured` + 治理事件计数，无 API Key |
| Claude Code 独立验收（未修改生成文件） | `python -m pytest /tmp/aegis-e2e-0h162mbh -q` → `1 passed in 0.00s`（`test_add_basic` 含全部 4 条断言：add(1,2)==3 / add(10,20)==30 / add(123,456)==579 / add(7,8)==15） |

**E2E RESULT: PASS**（完整脚本输出与生成文件内容见 `docs/AGENT_LOG.md` 「真实 LLM 端到端验收」节）

**Milestone 8 自动测试（零网络）：** `make test` → **442 passed**（419 基线 + 23 新）；`make demo` → **3 passed, 0 failed**

---

## 总体验收

当前 worktree(`webui-mock-demos`,追加任务 C)复跑:`make test` → **419 passed**(1 warning,starlette/httpx 弃用提示,非本项目代码);`make demo` → **3 passed, 0 failed(exit 0)**(Demo 1 危险拦截 / Demo 2 反馈回灌 / Demo 3 审批绑定,均 MockLLM 驱动、零网络)。PLAN 32 个原始 task 全部 `✅ DONE` 且带 commit hash + 追加任务 A/B/C/D;SPEC_PROCESS 五要素齐全。矩阵中每条要求均映射到可定位的实现文件、自动测试与演示证据。**WebUI 公网部署已完成**(追加任务 B,https://aegiscode-o20h.onrender.com);**WebUI 预设 MockLLM 演示**(追加任务 C)实现 + 自动测试 + 本地 Docker Demo Mode 实测 + **公网人工验收(2026-07-16,PR #12 → main `fb7029f` → Render 重部署)全部通过**(见上「WebUI 预设 MockLLM 演示」矩阵与 AGENT_LOG)。**真实 LLM Provider 可用性**(追加任务 D)：DeepSeek 驱动端到端验收通过，完整治理路径（解析→治理→HITL 审批→工具执行→pytest 验证→COMPLETED）实测证明（见上「追加任务 D」矩阵与 AGENT_LOG）。
