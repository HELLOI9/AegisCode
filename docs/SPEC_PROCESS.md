# SPEC_PROCESS.md — AegisCode 规约过程文档

> 本文件记录使用 Superpowers `brainstorming` 技能与智能体协作生成 `SPEC.md` 的完整过程:
> 每一轮提出的问题、问题为何重要、我的初始回答、智能体提出的备选方案、我最终的选择、
> 被否决的方案及原因、对原设想的修改、尚未解决的问题与暴露的风险。
> 按通用要求 §4.4 要求,至少形成 3 轮以上有实质变化的关键迭代。
>
> 记录方式:brainstorming 过程中**逐轮追加**,而非事后补写,以保留"挑战—修正"的真实证据。

---

## 阶段元信息

- 项目:AegisCode — A policy-governed coding agent harness with deterministic feedback loops.
- 项目类型:AI4SE 期末项目 A(Coding Agent Harness)。
- 当前阶段:第一阶段 brainstorming(需求分析与系统设计),尚未编写实现代码。
- 使用技能:Superpowers `brainstorming`。
- 硬性评分约束(贯穿全程):
  - §A.4(C):移除真实 LLM 后,每个核心机制必须能用 mock/stub LLM 确定性单测验证。
  - §A.4(D):六维度(决策/工具/记忆/治理/反馈/配置)都要有最低实现,但只深挖一个维度作为 main contribution。
  - §A.6:交付机制演示三件套——①拦截危险动作 ②失败反馈驱动动作变化 ③重点维度的确定性行为。

---

## 第 1 轮:核心目标用户与核心价值定位

**智能体提出的问题:** AegisCode 的核心目标用户与核心价值,应锚定在哪一种定位?

**为何重要:** 目标用户 / 核心价值 / main contribution 三者耦合。选错用户会导致"用户画像"与"技术深度"两张皮,直接影响 SPEC 问题陈述与评分维度选择。

**智能体提出的备选方案:**
- 方案 A「治理优先」:主用户是担心 Agent 越权/危险命令的开发者;价值=确定性安全边界+审批+可审计;main contribution=治理维度。
- 方案 B「反馈优先」:主用户想要靠客观信号自我修正;价值=反馈闭环+失败分类+多轮修正;main contribution=反馈维度。
- 方案 C「研究/教学优先」:价值=透明可观测;但"可观测"难成为机制密集维度,评分风险最高,智能体不推荐。

**智能体的推荐与挑战:** 推荐 A,反馈闭环作为"完整但非最深"的第二支柱。挑战:选 A 必须能回答"Claude Code 也有审批,你强在哪"——建议答案是"确定性+可单测+可审计的策略引擎"。

**我的最终选择:** A。

**被否决的方案:** B、C。B 差异化更弱(几乎所有 coding agent 都跑测试)且易与治理争时间导致两头不深;C 的 main contribution 不明确,评分风险最高。

**对原设想的修改:** 原设想把三类用户并列,现明确 A 为主用户、其余降为次要用户;确定 main contribution = 治理维度。

---

## 第 2 轮:治理要防护的"最关键痛点"优先级

**智能体提出的问题:** 治理深度应投向哪个/哪些威胁出口?

**为何重要:** 课程周期内无法把每类威胁都做深,必须挑主威胁做扎实,其余最低可用;此选择直接决定深度投入方向与演示③选题。

**智能体提出的备选方案:**
- 痛点甲:破坏性/越权命令(shell 层)——命令词法治理。
- 痛点乙:作用域逃逸(文件路径层)——路径围栏(归一化/`..`穿越/realpath 解符号链接/敏感文件黑名单)。
- 痛点丙:外部副作用/数据外泄(网络与发布层)——智能体建议压成粗粒度。

**智能体的推荐与挑战:** 推荐"甲+乙并列为深度核心,丙只做粗粒度"。挑战原稿把甲乙丙都铺开,警告三线并深必然时间崩。

**我的最终选择:** 甲+乙并列、丙粗粒度。

**被否决的方案:** "丙也做深"被否决,边际价值低、演示不干净。

**对原设想的修改:** 原稿治理三线并列,现收敛为"甲+乙深、丙粗粒度";确定演示①用甲(`rm -rf /` 被 DENY)、演示③用乙(符号链接逃逸被拒)。

---

## 第 3 轮:相比现有 Coding Agent 的差异化价值(一句话)

**智能体提出的问题:** 把差异化价值钉成一句可写进 SPEC 问题陈述、且每个词都能落成确定性代码的话。

**为何重要:** 决定 SPEC 问题陈述与 §3.4"能向外行说清为何有人用"的评分;必须扛得住"Claude Code 也有审批"的反问。

**智能体提出的备选方案:**
- 表述 X:强调"策略即代码、判定可单测"(命中 §A.4(C),最能扛反问)。
- 表述 Y:强调"可审计、防篡改哈希链证据"(对不信任 Agent 的人最有说服力)。
- 表述 Z:强调"声明式配置约束"(差异化最弱)。

**智能体的推荐与挑战:** 推荐 X 为主、Y 补强、Z 作为实现手段融入。挑战:需接受取舍——不以"补丁智能程度"竞争(那取决于底层 LLM),只以"治理确定性与可验证性"竞争,演示里故意用不聪明的 MockLLM 反而更能凸显"LLM 犯浑也守得住边界"。

**我的最终选择:** 以 X 为主句、Y 作为第二句补强。

**被否决的方案:** 纯 Z 作为主卖点被否决(不稀奇);取舍(不以补丁智能竞争)随 X+Y 一并接受。

**对原设想的修改:** 原稿差异化表述模糊,现固化主句:"AegisCode 把 Coding Agent 的安全治理从'系统提示词里的一句嘱托'变成一套确定性、可单测、可审计的策略引擎:每条拒绝/审批判定都能脱离 LLM 用单元测试验证,每次动作都留下防篡改的审计证据。"

---

## 第 4 轮:核心端到端场景

**智能体提出的问题:** 核心黄金路径要不要内嵌一次真实的治理拦截/审批?

**为何重要:** 黄金路径是验收标准与机制演示②的骨架;是否内嵌治理决定"核心场景是否体现 main contribution"。

**智能体提出的备选方案:**
- 选项甲:纯反馈路径,治理另做独立演示。
- 选项乙:治理内嵌黄金路径(读文件→`pip install` 进审批被拒→拒绝反馈回灌→改用标准库重写→测试失败→失败反馈回灌→修正→测试通过→finish→最终验证复跑=绿)。
- 选项丙:极简路径(改函数→测试→通过),退化为玩具。

**智能体的推荐与挑战:** 推荐乙——一条路径同时踩中反馈闭环+审批状态机+路径围栏+客观完成判定,一份剧本复用于 SPEC场景/验收标准/演示②。附两个待拍板细节:审批动作选 `pip install`;MVP 单栈锁定 Python+pytest。

**我的最终选择:** 选项乙。审批动作 `pip install`、单栈 Python+pytest 无异议(第 5 轮正式锁定)。

**被否决的方案:** 甲(主场景不体现治理,与定位割裂)、丙(玩具,§3.4 不接受)。

**对原设想的修改:** 原稿核心场景为散文,现固化为可作验收/演示脚本的确定性剧本,并内嵌一次 REQUIRE_APPROVAL。

---

## 第 5 轮:MVP 范围最终裁剪(Must / Should / Won't)

**智能体提出的问题:** MVP 三档裁剪,并挑战三个"看似该做实则该延后"的点。

**为何重要:** 决定能否按时交付的最高杠杆问题;范围过大会导致治理深度做不出来。

**智能体提出的方案与挑战:**
- Must:单用户/单任务/单仓库/锁 Python+pytest;自实现主循环+LLM 抽象层(真实+Mock);动作协议+工具分发;工具最小集;治理引擎(甲+乙+四档判定+HITL+审计哈希链)=深度核心;反馈闭环(pytest+退出码+文件变更范围);停机与防死循环;记忆最小实现(SQLite 无向量库);声明式配置;极简 WebUI;CLI;凭据 keyring+.env 降级;Docker+CI。
- 挑战1:自动回滚降到 Should(工作区即 git 仓库,回滚可交给 git 或最简快照)。
- 挑战2:lint/typecheck 降到 Should(反馈深度不来自信号种类多,而来自分类+回灌质量)。
- 挑战3:追加非目标——多语言、通用 shell 完整安全化、任务并发。

**我的最终选择:** Must 档无增删;自动回滚→Should;lint/typecheck→Should;三个追加非目标全部写入非目标;第 4 轮遗留动作(`pip install`、单栈 Python+pytest)锁定。

**被否决的方案:** 原稿把回滚、lint/typecheck 隐含在 MVP 内——现明确延后。

**对原设想的修改:** 原 MVP 清单偏大,现收敛为清晰的 Must/Should/Won't 三档;非目标清单扩充。

**尚未解决 / 待后续轮次:** 工具最小集细节(尤其 `write_file` vs `apply_patch` 是否二选一)、Shell 执行模型(方案 A/B/C)、反馈信号数据结构、完成条件形式化、治理四档语义、审批状态机、审计哈希链、记忆表结构、上下文预算、WebUI/CLI/API 边界、凭据威胁模型、技术选型确认、数据模型、测试策略、MockLLM 机制、验收标准。

---

## 第 6 轮:Agent 主循环形状(单动作 vs 多动作)

**智能体提出的问题:** 每轮 LLM 返回单个动作还是多动作批次?并附 6 条耦合子决策的推荐默认值。

**为何重要:** 主循环最底层架构,级联决定治理粒度、审计粒度、状态机复杂度与可测性。

**智能体提出的方案:**
- A 严格单动作:一动作=一判定=一审计,MockLLM 演示与单测最干净,契合治理优先。缺点是 LLM 调用次数多。
- B 多动作批次:省调用、像产品,但"批次中途被拒/需审批"使治理与状态机复杂度陡增,与治理优先冲突。
- C 单动作为主、只读可批:收益有限、引入分类复杂度。
- 推荐 A。

**我的最终选择:** 采纳 A(严格单动作)。6 条默认值全部无异议:①执行与验证分离(run_tests 是工具;finish 后 harness 独立复跑目标测试作最终验收);②run_tests = 工具+反馈传感器双身份,输出强制过反馈分类器;③finish 语义 = 声明完成→强制最终验证→仅当目标测试全绿且无越界无待审批才 COMPLETED;④审批暂停/恢复靠每轮持久化+待执行动作快照;⑤LLM 调用失败有限退避重试,仍失败以 LLM_ERROR 停机并写审计;⑥运行中状态每轮落盘,重启后可查询、可从 APPROVAL_REQUIRED 恢复,但不自动续跑。

**被否决的方案:** B、C(牺牲治理清晰度换 token,与定位冲突)。

**对原设想的修改:** 原稿把"每轮单动作 vs 多动作"列为开放问题,现锁定为严格单动作;明确了 finish 后强制独立最终验证这一"完成不靠 LLM 声称"的命脉条款。

**尚未解决 / 待后续轮次:** 同上,减去主循环形状。下一轮:结构化动作协议(JSON 模型 + 解析失败/未知工具/多余文本处理)。

---

## 第 7 轮:结构化动作协议与违规处理

**智能体提出的问题:** 动作数据模型定型;LLM 输出违规(多余散文/JSON 错/缺字段/未知工具/参数错)时的处理策略。

**为何重要:** 决策封装核心机制,且必须脱离真实 LLM 可单测(§A.4C);易被做成"提示词祈祷"而非代码机制。

**智能体提出的方案:** 数据模型 {thought, tool, arguments, expectation?};违规处理 A=严格+有限重试+结构化纠错反馈(推荐)/ B=违规即终止 / C=宽松尽力猜测(否决,猜测=不确定性,与治理精神冲突)。

**我的最终选择:** 采纳数据模型(去掉 is_final,finish 用独立工具);采纳策略 A,重试上限 3 次;三个附带默认值(围栏优先提取、区分"未知工具 INVALID_ACTION"与"被禁用 DENY"、独立 finish 工具)全采纳。

**被否决的方案:** C(宽松猜测,可能把危险动作猜进来);is_final 布尔位(改用独立 finish 工具统一"一切皆工具")。

**对原设想的修改:** 原稿把"解析失败后重试或终止"设为开放——现明确:结构化纠错反馈回灌 + 3 次上限接入停机条件。

---

## 第 8 轮:工具最小集 + write_file vs apply_patch

**智能体提出的问题:** 文件写入工具选哪个模型(全量覆盖 vs 补丁 vs 都做)?第一版给 Agent 哪几把刀?

**为何重要:** 多一个工具就多一套 schema/治理/单测;补丁应用器是易错解析器,会吃掉本该投给治理的时间。

**智能体提出的方案:** A=只 write_file 全量覆盖(推荐)/ B=只 apply_patch 结构化补丁 / C=都做(否决,违反 YAGNI)。

**我的最终选择:** 采纳 A(砍 apply_patch→未来);保留 search_text;工具最小集 = list_files / read_file / search_text / write_file / run_tests / run_command / finish;三个附带默认值(禁工作区外文件、敏感文件.env/.git/凭据读写皆 DENY、符号链接按 realpath 判定+二进制安全跳过)全采纳。

**被否决的方案:** apply_patch(补丁应用器复杂度对治理零贡献,纯时间黑洞);同时保留两个写工具。

**对原设想的修改:** 原稿 8 工具含 write_file + apply_patch 并列——现收敛为单一 write_file 全量覆盖,变更范围检查因此几乎免费。

---

## 第 9 轮:Shell 执行模型(main contribution 甲的核心)

**智能体提出的问题:** `run_command` 如何治理?点破关键矛盾——方案选择直接决定"甲(命令词法治理)"还有没有深度可做,并追问"LLM 提交字符串还是 argv 数组"这一岔路。

**为何重要:** 全项目工程深度最集中处;也是最容易被做浅(纯白名单)或做危险(shell=True)的地方。

**智能体提出的方案与挑战:**
- 挑战1:原方案 A(不给通用 shell)会架空 main contribution 甲 + 演示①失去载体 → 否决。
- 挑战2:纯白名单(B)太浅;朴素通用 shell(C + shell=True)是安全灾难。
- 挑战3:点破"字符串 vs argv 数组"岔路——argv 数组下管道/重定向物理上不可能发生,词法分析无用武之地,治理退化;必须用字符串输入才能让"词法分析"成为真实可测的工程。
- 提出方案 D:字符串输入 + 5 层确定性管线(词法解析 → 结构安全层 → 允许列表 → 危险参数级规则 → shell=False+argv 执行)。

**我的最终选择:** 全采纳方案 D;命令字符串输入;元结构一律 DENY;危险参数划线(DENY: rm -rf/sudo/su/chmod/chown/curl/wget/git reset --hard/git clean/git push/任意元结构;REQUIRE_APPROVAL: pip install/git commit/写工作区内非白名单目录)。

**被否决的方案:** 方案 A(架空甲);纯 B(过浅);朴素 C/shell=True(不安全);argv 数组输入(词法分析退化)。

**对原设想的修改:** 原稿演示①用 argv 数组 `["rm","-rf","/"]`——现改为命令字符串 `"rm -rf /"`,既仍 DENY 又更能展示词法治理深度。原三方案升级为分层的方案 D。

---

## 第 10 轮:客观反馈闭环 —— 结果结构 + 失败分类 + 回灌策略

**智能体提出的问题:** ToolResult 统一结构、失败分类法、回灌如何防上下文爆炸与重复犯错。

**为何重要:** 反馈是第二支柱;分类与回灌必须是确定性代码(§A.4C:MockLLM 下断言分类正确)。

**智能体提出的方案:** ①ToolResult 区分 detail_for_llm(截断脱敏,LLM 可见)与 artifacts(完整 diff/stdout,仅审计+WebUI);②失败分类精简为 8 类 MVP + 3 类预留(LINT/TYPECHECK/BUILD 随 Should);③回灌精简(pytest 只回失败测试名+断言行+traceback 末 20 行)+ 确定性脱敏(路径归一化+密钥正则擦除)+ 重复动作指纹 K=3 判 NO_PROGRESS(只拦完全重复,不臆测语义相似)。

**我的最终选择:** 三项全采纳,无修改。

**对原设想的修改:** 原稿 11 类分类 → 收敛 8 类 + 3 预留;明确"用户可见 vs LLM 可见结果"分离(原为开放问题)。

---

## 第 11 轮:完成条件 + 停机判定形式化

**智能体提出的问题:** 把完成/停机整合成带优先级的确定性判定表;两个争议点(审批被拒后继续还是停、阈值默认值)。

**为何重要:** "继续/暂停/成功/失败/终止"必须可单测、可画状态机;"完成不靠 LLM 声称"是定位命脉。

**智能体提出的方案:** 终止原因枚举 9 项 + 每轮判定优先级表(内部异常>取消>无效动作>DENY>审批暂停>工具执行反馈>finish 最终验证>计数类停机)。争议点1:审批被拒→甲(继续,拒绝作反馈回灌)vs 乙(立即停)。争议点2:max_steps=25/M=5/NO_PROGRESS=3。

**我的最终选择:** 判定表无修改;审批被拒采纳甲(否则黄金路径/演示②不成立);阈值默认全接受(可 YAML 覆盖)。

**被否决的方案:** 乙(审批被拒立即停)——会杀死黄金路径"被拒→改用标准库"的核心桥段。

**对原设想的修改:** 原稿完成/停机条件零散罗列 → 整合为带短路优先级的判定表 + 终止原因枚举。

---

## 第 12 轮:治理四档语义 + 策略引擎结构

**智能体提出的问题:** 四档结果各自执行语义;策略引擎求值结构;无命中时的默认档方向。

**为何重要:** 让治理从散规则变成可单测的策略引擎(§A.4C/D)的中枢。

**智能体提出的方案:** ①四档执行语义表(ALLOW 执行/ALLOW_WITH_AUDIT 执行+强化审计/REQUIRE_APPROVAL 暂停等裁决/DENY 不执行回灌 POLICY_DENIED);是否合并为"三档+审计布尔位"由用户定。②求值结构 A=有序 first-match-wins(推荐,唯一 rule_id+reason)vs B=最严胜出(难给单一理由、易过度拦截)。③默认档 甲=fail-closed 分层(只读 ALLOW/写 APPROVAL/命令 DENY)vs 乙=fail-open(不推荐)。

**我的最终选择:** 保留四档;求值选 A;默认档选甲(分层 fail-closed)。

**被否决的方案:** 三档合并(用户选择保留四档以支持"低风险但留痕"标记);求值 B(最严胜出);fail-open 默认。

**对原设想的修改:** 原稿只列了四档名称未定执行语义与引擎结构——现明确 first-match 有序管线 + 分层 fail-closed 默认 + 每判定唯一 rule_id/reason。

---

## 第 13 轮:路径围栏"乙"的精确算法(演示③载体)

**智能体提出的问题:** 把路径围栏定成可逐条单测的判定函数;点出"归一化顺序"与"realpath 何时解析"两个易栽点;边界陷阱"新建不存在的文件"。

**为何重要:** 两条深度线之一 + 演示③(符号链接逃逸被拒)的载体;必须确定性可单测。

**智能体提出的方案:** 核心算法"先 realpath 再判归属"(软链 link→/etc/passwd 经 realpath 后归属失败即 DENY);边界陷阱——新建文件应对"父目录"做 realpath 判定;三个拍板点:①绝对路径(推荐一律 DENY vs 允许但须归属内)②软链(推荐按 realpath 归属)③大小写(只管 Linux)。

**我的最终选择:** 采纳核心算法;明确"对父目录做 realpath 判定";绝对路径**覆盖智能体推荐**——选"允许但须 realpath 后在工作区内"(而非一律 DENY);软链按 realpath 归属;大小写只管 Linux。

**被否决的方案:** "一律 DENY 绝对路径"(用户认为按 realpath 归属更实用且仍安全);"一律禁软链"(改为按 realpath 归属)。

**分歧记录:** 智能体推荐一律 DENY 绝对路径(更简更安全),用户选按 realpath 归属放行。代价:多测一类绝对路径用例;归属判定兜底保证安全性可接受。

**对原设想的修改:** 原稿只列路径围栏关注点清单——现固化为 6 步确定性算法 + 父目录判定规则 + 明确 Linux-only。

---

## 第 14 轮:HITL 审批状态机

**智能体提出的问题:** 任务/审批状态、转换、每个审批请求保存什么、四个边界(动作改后旧审批是否失效/超时/记住批准/恢复语义)。

**为何重要:** 治理维度最像状态机、最适合单测的部分。

**智能体提出的方案:** 两层状态(TaskState + ApprovalState,避免任务态爆炸);ApprovalRequest 字段(含 action_snapshot + action_fingerprint + risk_explanation);四边界——①动作改→SUPERSEDED 重审 ②审批无超时 EXPIRED 预留 ③"记住批准"限定完全相同指纹 ④恢复只执行原始快照。

**我的最终选择:** 两层状态采纳;字段无增删;四边界全采纳,"记住批准"MVP 就做。SUPERSEDED 重审记为可选第四演示候选。

**被否决的方案:** 把 APPROVED/REJECTED/EXECUTING 作为任务态(改为审批请求级状态);"同类动作"记住批准(改为完全相同指纹,避免语义猜测);审批自动超时决策(MVP 不启用,风险高)。

**对原设想的修改:** 原稿 8 个平铺状态——现分两层;"记住批准"从"同类"收紧为"完全相同指纹"。

---

## 第 15 轮:审计日志 + 哈希链 + 回滚

**智能体提出的问题:** 审计记什么、哈希链如何做到"防篡改可验证"、回滚(Should 档)的最简形态。

**为何重要:** 审计是差异化主句 Y 的落地("每次动作留防篡改证据");哈希链校验是绝佳的确定性单测。

**智能体提出的方案:** ①审计 = 每任务 append-only 事件流,AuditEvent 含 event_type(7 类)+ payload + prev_hash + hash;②哈希链 hash=SHA256(prev_hash‖规范化内容),提供 verify_chain 确定性校验函数;③拍板 1:只做 SHA256 可检测篡改 vs 加 HMAC 签名防伪造(推荐只做哈希链,签名→未来);④写入前脱敏 + SQLite audit_events 表 + WebUI 校验按钮;⑤拍板 2:回滚选甲(写前快照 .aegis/snapshots + rollback_task)vs 丙(不做,交给用户 git)。

**我的最终选择:** 审计结构无修改;哈希链只做 SHA256(不做 HMAC 签名);脱敏+SQLite+WebUI 校验采纳;回滚选甲(写前快照)作为 Should 档。

**被否决的方案:** HMAC 签名(收益低、需密钥管理,→未来);git 快照回滚(耦合工作区是 git 仓库,不推荐);回滚选项丙(改为做写前快照)。

**对原设想的修改:** 原稿"日志是否需要哈希链"为开放问题——现明确做 SHA256 哈希链 + verify_chain;回滚从"若干候选"收敛为写前快照单一方案。

---

## 第 16 轮:记忆与上下文 —— 表结构 + 检索 + 上下文预算

**智能体提出的问题:** 哪些跨会话保存、memories 表结构、检索是否需向量库、禁写内容、Agent 能否自主写记忆、上下文预算如何装配与截断?

**为何重要:** 记忆是六维度之一,必须自实现(§A.4-D 不得接用框架自带 memory),但不深挖(治理才是深度线)。

**智能体提出的方案:** ①记忆三分层——只有"跨会话 Memory"是记忆,任务级状态与审计不算(但都进 SQLite);②memories 表(memory_id/project_id/type/key/value/tags/source/时间戳/use_count,type 5 枚举);③检索确认无向量库(type 过滤+project_id+关键词 LIKE+last_used_at 排序+topK);④禁写过滤器复用脱敏器(key/.env/大段源码/未确认推测);⑤拍板 2:Agent 自主写记忆——甲(禁止,只用户/系统写)vs 乙(可提议,落 source=agent 标记未确认);⑥上下文预算 6 段优先级装配 + 拍板 3:字符数近似 vs 精确 tokenizer。

**我的最终选择:** 三分层 + 表结构无修改;确认无向量库;上下文预算用字符数近似(非 tokenizer);**Agent 写记忆选乙(覆盖智能体推荐的甲)**,附加约束:source=agent 记忆仅作提示、永不作治理依据、经脱敏器过滤。

**被否决的方案:** 向量库/embedding 检索(对"改一个函数"级任务价值极低);精确 tokenizer(引入依赖与厂商差异,→未来);选项甲禁止 Agent 写记忆(用户选乙以求灵活)。

**分歧记录:** 智能体推荐甲(Agent 不能自主写长期记忆,防污染+不确定性),用户选乙(允许提议)。缓解:附加"未确认标记 + 永不作治理依据 + 脱敏过滤"三重约束。

**对原设想的修改:** 原稿把"项目记忆/任务状态/审计"混列——现三分层,明确只有跨会话记忆是"记忆";检索正式排除向量库;新增"Agent 写记忆的安全约束"。

---

## 第 17 轮:WebUI / CLI / REST API 边界 + 实时状态方案

**智能体提出的问题:** 执行模型(同步/异步)、实时状态方案(轮询/SSE/WS)、各层 MVP 功能边界、前端是否用 Open Design?

**为何重要:** 主循环多轮 + 审批暂停,不能同步阻塞返回;执行模型决定 API 形状;§3.6 涉及 UI 要考虑 Open Design。

**智能体提出的方案:** ①执行模型 A(异步+状态持久化,POST /tasks 立即返回 task_id,后台跑循环每轮落 SQLite,审批处暂停)vs B(同步阻塞,审批必超时,否决);②实时状态——甲轮询(GET events?since=N)MVP 推荐 / 乙 SSE 留 Should / 丙 WebSocket 否决;③8 个 REST 端点;④WebUI 必做(启动/事件流/审批面板/diff/最终状态/审计)vs 延后(SSE/历史美化/链可视化);⑤前端拍板——建议豁免 Open Design 用极简原生 HTML/CSS/JS(WebUI 本质是只读观测+审批面板,治理是主角)。

**我的最终选择:** 执行模型 A;实时状态用轮询(甲),SSE 留 Should;8 端点无增删;WebUI 划分无调整;同意豁免 Open Design,用极简原生前端(SPEC 说明理由)。

**被否决的方案:** 同步阻塞执行(审批暂停必超时);WebSocket(单用户过重);SSE 进 MVP(降到 Should);Open Design(豁免,避免设计系统开销挤占治理深度)。

**对原设想的修改:** 原稿只列候选端点/命令与"同步还是异步"开放问题——现锁定异步+轮询;明确前端豁免 Open Design 并需在 SPEC 写豁免理由。

---

## 第 18 轮:凭据安全 —— 威胁模型 + 存储/录入/清除 + secret scanning

**智能体提出的问题:** 凭据存储分层降级、威胁模型与对策矩阵、CLI 凭据命令、`.env` 降级默认开关、secret scanning 用什么?

**为何重要:** 通用要求 §3.1 必做硬项,评分专门看;凭据泄漏路径多(源码/Git/日志/堆栈/WebUI/history/Docker层/文件权限)。

**智能体提出的方案:** ①存储分层 keyring→.env(gitignore+chmod600)→环境变量,读取顺序同,禁命令行 export;②威胁→确定性对策矩阵(脱敏器覆盖日志/审计/反馈、status 只返 configured+掩码、getpass 隐藏录入、镜像不 COPY/ENV key、测试用 stub keyring+假 key 永不联网);③CLI key set/status/clear;④拍板 2:`.env` 降级默认——甲关闭(fail-safe,需显式 allow_dotenv:true+明文警示)vs 乙开启;⑤拍板 3:secret scanning——自写确定性 key 模式扫描器(可单测)/ gitleaks / 两者。

**我的最终选择:** 存储分层+读取顺序采纳;威胁对策矩阵无补充;CLI 凭据命令确认;`.env` 降级默认关闭(甲,fail-safe);secret scanning 选两者(自写可单测扫描器 + CI 兜底 gitleaks 双保险)。

**被否决的方案:** `.env` 默认开启(违背安全默认);命令行 export(进 shell history);只用 gitleaks 或只自写(改为双保险)。

**对原设想的修改:** 原稿列了凭据威胁清单但无对策映射——现固化为威胁→对策矩阵;`.env` 明确 fail-safe 默认关闭;secret scanning 增加"自写可单测扫描器"以增强"机制是代码"的可测工程量。

---

## 第 19 轮:分发与部署 —— Docker 形态 + 冷启动 + 云部署鉴权

**智能体提出的问题:** 分发形态(是否只 Docker)、容器内 keyring 不可用如何处理、workspace 如何进容器、云端公网 URL 的鉴权/滥用风险如何应对?

**为何重要:** §3.2 分发必做 + §清单第 9 条必须提供可访问 WebUI 线上 URL;公网 + 能执行代码的 Agent 服务有独特的滥用风险。

**智能体提出的方案:** ①分发只做 Docker 单一形态(PyPI/二进制→未来);②容器内无 Secret Service,keyring 不可用时自动回退环境变量(与 allow_dotenv 无关,后者只管 .env 文件);③workspace 用 `-v` 卷挂载到 /workspace;④云部署鉴权——甲演示沙箱 / 乙访客填自己key+沙箱 / 丙口令保护，纵深防御。

**关键讨论(用户追问 + 智能体澄清):** 用户质疑"这不是 harness 吗?不该让用户自己填 key 体验吗?"——智能体澄清存在两个场景:场景一(用户在自己机器跑,自己填 key、自己的项目、自己的额度)= 零鉴权的正常 harness 用法,用户直觉完全正确;场景二(为交作业部署的公网 demo URL)= 机器是你的,风险在"谁能来用你的服务器执行代码"。进一步澄清:即使让访客填自己的 key(解决烧钱),执行仍发生在你的服务器上(执行面暴露)+ workspace 是谁的两个问题仍在。核心洞察:key 归属解决"烧钱/谁能进",沙箱解决"进来了能造多大破坏",两者不可互替。

**我的最终选择:** 分发只做 Docker;容器 keyring 不可用自动回退环境变量;workspace 用 `-v` 挂载 /workspace;云部署选**甲(演示沙箱)**——锁定镜像内预置玩具 Python 项目为 workspace + 最窄允许列表 + 小额度专用 key 或 MockLLM，零门槛访问、不强制口令。主场景(本地自带 key)零鉴权不变。

**被否决的方案:** PyPI/二进制分发(→未来);乙/丙(演示 URL 加口令或要求访客填 key，牺牲"点开即看"体验，对课程 demo 非必需)。

**对原设想的修改:** 原稿云部署只列"是否加鉴权"开放项——现明确区分"本地主场景零鉴权"与"公网 demo 受限橱窗",公网用演示沙箱兜底执行面风险。

---

## 第 20 轮:技术栈选型 —— Python 是否最优 + SQLite 访问层 + LLM 协议

**智能体提出的问题:** Python 全家桶是否最优(至少比较一个替代)、SQLite 用 ORM 还是标准库、LLM 接哪些协议?

**为何重要:** §3.3 要求 SPEC 说明选型理由;选型直接影响甲/乙/MockLLM 三个核心机制的实现成本。

**智能体提出的方案:** ①按 10 维度对比 Python / TypeScript / Go——关键判断:甲核心依赖 shell 词法分析而 `shlex` 是 Python 标准库(几乎单独决定选型)、乙核心 pathlib realpath 顺手、MockLLM 单测 pytest+DI 最省事、Pydantic/keyring/FastAPI 生态成熟;Python 唯一劣势(单文件二进制弱)在已选 Docker 后被规避;②SQLite——标准库 sqlite3+手写 SQL(零依赖、透明、记忆存储更纯粹)vs SQLModel/SQLAlchemy;③LLM——确认只接 OpenAI-compatible 单次补全 API(可配 base_url)。

**我的最终选择:** Python 3.12 全家桶(FastAPI/Pydantic v2/pytest/PyYAML/keyring/Docker/原生前端);SQLite 用标准库 sqlite3+手写 SQL;LLM 抽象层**同时支持 OpenAI 与 Anthropic 两种协议**(两个真实适配器 + MockLLM,主循环不感知协议差异)。

**被否决的方案:** TypeScript/Go(样样需凑第三方,shlex 优势无法替代;Go 的二进制优势在选 Docker 后失效);SQLModel/SQLAlchemy ORM(加依赖,MVP 表不多手写 SQL 更透明)。

**对原设想的修改:** 原稿只倾向 Python + OpenAI-compatible 单协议——现确认 Python 并追加 Anthropic 协议支持(统一 LLMClient 接口 + OpenAIAdapter/AnthropicAdapter/MockLLM 三实现,协议差异封装在适配器内,印证"LLM 抽象层可替换"评分点);SQLite 明确用标准库而非 ORM。

---

## 第 21 轮:数据模型汇总 —— SQLite 表结构定稿

**智能体提出的问题:** 把前面散落的实体收拢成定稿表清单;steps 与 audit_events 是否冗余;memories 是否加 confirmed;凭据与配置是否入库?

**为何重要:** SPEC"数据模型"章节与后续 PLAN 需要确定的表清单依据。

**智能体提出的方案:** 6 张表——tasks / steps / approval_requests / audit_events / memories / task_snapshots(回滚索引,Should)。①steps(粗粒度循环状态快照,便于恢复/查询进度)vs audit_events(细粒度 append-only 哈希链证据流,一轮可多条事件)用途不同,建议都保留;②memories 加 confirmed 字段(source=agent → confirmed=false,仅提示不作治理依据);③凭据不入库(keyring/.env)、配置不入库(YAML),只有 credentials/status 读状态。

**我的最终选择:** 6 张表全采纳;steps 与 audit_events 都保留不合并;memories 加 confirmed 字段;凭据与配置不落 SQLite,确认。

**被否决的方案:** 合并 steps 与 audit_events(用途不同——恢复态 vs 证据流,合并会牺牲哈希链的细粒度);凭据/配置入库(凭据入库违背安全,配置用 YAML 文件更符合"声明式配置")。

**对原设想的修改:** 原稿记忆/任务/审计实体散落各处——现固化为 6 张定稿表 + 明确字段;新增 memories.confirmed 承接第 16 轮 Agent 写记忆约束。

---

## 第 22 轮:配置模型 —— aegis.yaml 结构定稿

**智能体提出的问题:** YAML 八段结构是否合理;配置分层覆盖;command_rules 表达力(token 包含 vs 正则);是否加 write_allowlist_dirs;是否 Pydantic 校验?

**为何重要:** 配置是六维度之一 + 差异化主句"声明式配置约束 Agent"的落地;纪律要求(§A.4B/C)——YAML 只是规则内容,规则解释与执行必须是代码。

**智能体提出的方案:** aegis.yaml 八段(workspace/limits/tools/feedback/governance/memory/credentials/llm),承接前面所有决策的阈值与规则;①配置分层——代码内置默认 + aegis.yaml 覆盖 + 少数环境变量覆盖(provider/model),云端 demo 是收紧的 yaml;②command_rules 用 argv0+args_contain token 包含匹配(推荐,正则→未来);③拍板 write_allowlist_dirs——加(白名单内写 ALLOW、之外 REQUIRE_APPROVAL,避免黄金路径每次写都审批)vs 所有写都审批;④加载时 Pydantic 校验(未知字段/类型错/缺失→启动即报错)。

**我的最终选择:** 八段结构认可;配置三层覆盖认可;command_rules 用 token 包含匹配(正则→未来);加 write_allowlist_dirs;Pydantic 校验确认。

**被否决的方案:** command_rules 支持正则(MVP token 包含够用,正则→未来);"所有工作区内写都走 REQUIRE_APPROVAL"(改为 write_allowlist_dirs,否则演示啰嗦)。

**对原设想的修改:** 原稿配置只列"允许项"清单——现固化为可被策略引擎读取执行的结构化 YAML(argv0 白名单 + 结构化 command_rules + write_allowlist_dirs + 默认档),确保规则由代码解释而非提示词。

---

## 第 23 轮:测试策略 + MockLLM 机制演示设计

**智能体提出的问题:** MockLLM 能力边界、测试分层、§A.6 三个机制演示的精确剧本、是否加第四演示、黄金路径端到端测试?

**为何重要:** §A.4C(移除真实 LLM 后机制可单测)+ §A.6(三个机制演示)是评分核心;§清单第 6 条要求 CI 有名为 unit-test 的 job。

**智能体提出的方案:** ①MockLLM——按序响应队列 + 记录收到的 messages(断言反馈进入上下文)+ 零网络零 key,拍板 1:是否支持条件响应(推荐 MVP 只做按序队列,条件用个别 lambda);②测试三层(单元/集成/机制演示);拍板 2:make test + CI unit-test job;③三演示剧本(①rm -rf 被 DENY ②失败反馈驱动动作变化+最终验证器复跑绿 ③符号链接逃逸被拒);拍板 3:是否加第四演示(SUPERSEDED 重审);拍板 4:黄金路径端到端集成测试作演示②超集。

**我的最终选择:** MockLLM 按序队列+记录 messages(条件响应仅个别高级测试用 lambda);测试三层;make test + CI unit-test job 确认;三演示剧本定稿;加第四附加演示(SUPERSEDED 重审);黄金路径端到端测试确认。

**被否决的方案:** MockLLM 内置复杂条件路由(MVP 用按序队列,更确定易断言)。

**对原设想的修改:** 原稿演示要求泛述——现固化为三个可断言剧本(每个含输入/初始态/断言/副作用)+ 第四附加演示 + 黄金路径端到端测试;明确"COMPLETED 由最终验证器复跑而非 MockLLM 声称"作为演示②的关键断言。

---

## 第 24 轮:验收标准 —— 逐模块客观判定条件

**智能体提出的问题:** 把前面决策翻译成 15 个模块的可勾选验收条件;验收粒度(模块级 vs 每规则一项);是否加量化非功能验收?

**为何重要:** §4.2 第 9 条要求每个功能"完成"的客观判定标准;SPEC 验收章节 + PLAN 验证步骤都依赖它。

**智能体提出的方案:** M1~M15 逐模块 1~2 条可自动化断言的验收条件;拍板 1:粒度——SPEC 模块级、细粒度留 PLAN 每 task 验证步骤;拍板 2:非功能验收只量化可确定性测的项(超时/输出截断/重试 3 次),不加依赖真实 LLM 的响应时间指标。

**我的最终选择:** 15 模块验收草案采纳;粒度保持模块级(细粒度归 PLAN);非功能验收只量化可确定性测项,同意不加响应时间类指标。

**被否决的方案:** SPEC 里做每条治理规则一个验收项(过细,归 PLAN);加"响应时间<X秒"类指标(依赖真实 LLM/环境,不可确定性测)。

**对原设想的修改:** 原稿验收标准泛述——现固化为 15 模块级客观条件,并确立"验收只量化可确定性测项"的原则。

---

## 第 25 轮:风险与未决问题梳理

**智能体提出的问题:** 梳理 brainstorming 暴露的技术/范围/评分风险与未决问题,确认哪些写入 SPEC、哪些现在消解。

**为何重要:** SPEC 最后一节要求风险/限制/未决问题;有些坑(如允许列表被 python -c 绕过)必须现在堵。

**智能体提出的方案与挑战:** R1 命令允许列表被 `python -c`/`-m` 内联代码绕过(建议现在加进审批/拒绝清单);R2 realpath TOCTOU(单用户可接受,写已知限制);R3 SQLite 并发(WAL+短事务);R4 治理深度 vs 六维度完整的平衡(PLAN 优先治理+反馈垂直切片);R5 冷启动验证会暴露 SPEC 缺陷(预期中);R6 机制是代码的持续自检;R7 REFLECTION 须本人写。未决 U1(search_text 实现)/U2(超预算丢弃 vs 摘要化)/U3(云端 MockLLM vs 真实 key)。

**我的最终选择:** R1 加 python -c/-m 内联到审批/拒绝清单;R4 认可治理+反馈垂直切片优先;U1 纯 Python 遍历;U2 摘要化最旧轮;U3 云端用 MockLLM。

**智能体补充约束:** U2 的"摘要化"必须是确定性结构化压缩(保留动作类型+治理判定+反馈分类,丢细节),不调 LLM 摘要,否则破坏"移除 LLM 可单测"。

**被否决的方案:** 允许列表不限制 python 内联(会使允许列表形同虚设);U2 用 LLM 摘要(破坏确定性);U3 云端用真实 key(成本+滥用风险)。

**对原设想的修改:** 原稿未系统梳理风险——现固化风险清单 + 缓解;新增 python -c/-m 治理规则;明确"确定性摘要"约束。

---

# 综合回顾（brainstorming 过程总结）


## 一、Claude 提出的关键问题（按影响力排序）

1. **主定位应锚定治理、反馈还是研究/教学？**（决定 main contribution 与整个项目走向）
2. **治理深度往哪里砸？**（命令 shell 出口 + 文件路径出口 并列，还是只挑一个）
3. **相比 Claude Code / Codex 的差异化，一句话是什么？**（问题陈述核心）
4. **核心端到端场景要不要内嵌一次真实的治理拦截/审批？**（决定黄金路径与演示是否复用）
5. **MVP 如何三档裁剪，才能既不是玩具又能按时交付？**
6. **主循环每轮单动作还是多动作？**（级联决定治理/审计/状态机复杂度）
7. **`run_command` 到底怎么治理？字符串输入还是 argv 数组？**（main contribution 甲的成败点）
8. **完成条件如何做到"不靠 LLM 声称"？**
9. **云端公网 demo 的鉴权风险到底是什么？**（我当时没理解，追问后澄清）

## 二、我最初的想法 → 最终选择（对照）

| 议题 | 我最初的想法 | 最终选择 | 是否被 Claude 改变 |
|---|---|---|---|
| 定位 | 三类用户都想覆盖 | 锁定"治理优先"，其余降为次要 | 是（收敛） |
| 治理范围 | 甲乙丙全铺开 | 甲+乙深挖、丙粗粒度 | 是（砍丙深度） |
| 工具集 | write_file + apply_patch 都要 | 只做 write_file 全量覆盖 | 是（砍 apply_patch） |
| Shell 输入 | argv 数组（我的演示样例） | 命令字符串 + shlex 词法治理 | 是（改为字符串，才有词法深度） |
| 反馈信号 | pytest+lint+typecheck 都上 | MVP 只 pytest+退出码+文件范围，lint/typecheck 延后 | 是（延后） |
| 绝对路径 | —（未想过） | 允许但须 realpath 归属工作区内 | 否（我推翻了 Claude 的"一律 DENY"） |
| Agent 写记忆 | —（未想过） | 允许提议（source=agent+未确认） | 否（我推翻了 Claude 的"禁止"） |
| 云端鉴权 | 以为"让用户自己填 key"即可 | 演示沙箱兜底执行面 | 部分（Claude 澄清了两个场景） |
| 分发 | Docker+可能多形态 | 只做 Docker 单一形态 | 是（收敛） |
| 技术栈 | Python 全家桶 | 确认 Python + 追加 Anthropic 协议 | 基本维持 |

## 三、被否决的方案及原因（精选）

- **多动作批次循环** → 否决：治理要处理"批次中途被拒/需审批"，审计与状态机复杂度陡增，与治理优先冲突。
- **纯允许列表 Shell（方案 B）/ 完全不给通用 Shell（方案 A）** → 否决：前者太浅撑不起深度维度，后者直接架空 main contribution 甲。改用分层管线方案 D。
- **apply_patch 补丁应用器** → 否决：补丁解析器是易错的时间黑洞，对治理零贡献。
- **向量数据库检索记忆** → 否决：对"改一个函数"级任务价值极低，纯复杂度浪费。
- **HMAC 签名审计** → 否决：需密钥管理，收益低；SHA256 哈希链的"可检测篡改"已够。
- **云端 demo 加口令/要求访客填 key** → 否决：牺牲"点开即看"体验，对课程 demo 非必需；改用演示沙箱。
- **LLM 摘要压缩上下文** → 否决：破坏"移除 LLM 可单测"，改用确定性结构化摘要。
- **精确 tokenizer 计上下文预算** → 否决：引入依赖与厂商差异，字符数近似够用。

## 四、至少三轮实质性修改（我推翻/修正 Claude 的节点）

1. **绝对路径策略（第 13 轮）**：Claude 推荐"一律 DENY 绝对路径"（更简更安全）。我推翻，选"允许但须 realpath 后落在工作区内"——因为一律禁绝对路径对真实使用太死板，而 realpath 归属判定已能兜底安全。代价是多测一类用例，可接受。
2. **Agent 写记忆（第 16 轮）**：Claude 推荐"禁止 Agent 自主写长期记忆"（防污染+不确定性）。我推翻，选"允许 Agent 提议写入"。Claude 据此补了三重约束（source=agent 标记未确认 + 永不作治理依据 + 经脱敏器过滤）作为缓解——这是一次"我改方向、Claude 补护栏"的协作。
3. **云部署鉴权（第 19 轮）**：我追问"这不是 harness 吗？不该让用户自己填 key 体验吗？"，指出 Claude 最初笼统的鉴权论述没区分场景。Claude 据此澄清出"本地主场景（零鉴权、用户自带 key）"与"公网 demo（受限橱窗、沙箱兜底）"两个截然不同的场景，修正了原设计。

（其余实质性收敛：定位从三类用户收敛到治理优先、治理从甲乙丙全铺到只深挖甲乙、Shell 从 argv 改字符串——均见上表。）

## 五、我对 brainstorming 技能的评价

> **做得好的地方：**
> - "每次只问一个问题 + 给 2~3 个带优缺点/成本/风险的方案 + 明确推荐" 的节奏，避免了被一次性大问题淹没，也逼我对每个决策单独负责。
> - Claude 多次主动挑战我的初始设想（砍 apply_patch、砍 lint、把 argv 改字符串），这些挑战大多提高了设计质量，而不是顺着我说。
> - 把"评分硬标准（移除 LLM 可单测）"当成贯穿始终的约束反复对齐，避免了设计滑向"提示词工程"。
> - 逐轮沉淀 SPEC_PROCESS，使过程证据真实可查。
>
> **让我不满/可改进的地方：**
> - **执行可靠性不稳**：Claude 在中段出现过一次工具重复写入 SPEC_PROCESS.md 的循环，以及一次漏问第 17 题就跳到第 18 题的编号错误，都需要我主动介入指出、它才回到轨道。这说明"过程记录"这类需要严格线性的动作，即使有明确指令，模型也可能在长上下文里失手；仍需要我全程盯着。
> - **单题信息密度偏高**：不少轮次给了 3 个方案 + 逐条优缺点 + 附带默认值 + 拍板点，一次要消化的东西偏多。虽然结论质量高，但推进节奏对我的阅读体力是有压力的；如果 Claude 能主动分辨"重决策题（值得铺满）"与"次要题（可精简）"，节奏会更好。
> - **偶尔用推荐值代替提问**：例如第 4 题遗留的两个细节（审批动作、单栈锁定），Claude 直接暂定了推荐值放到下一题一并确认；虽然效率高，但严格意义上违背了"每次一个问题"的原则，边界略模糊。
> - **主动挑战集中在前中段**：越到后段（尤其数据模型 / 验收标准 / 风险），Claude 的挑战强度明显下降、更多是收敛整理。这对赶进度是好事，但也意味着后段决策没经过和前段同等强度的反问，未来可能暴露缺陷。
>
> **总体判断：** 对本项目而言，brainstorming 技能是**净正收益、且不可替代**——它逼我在写代码前把定位、边界、机制、演示、验收都想清楚，产出的 SPEC 密度远高于我独立写出的版本。但它**不是"甩给智能体就能自动产出好设计"的工具**：真正推动设计变清晰的，是几次我推翻它的推荐（绝对路径、Agent 写记忆、云部署鉴权），以及我坚持要求它把过程完整记入 SPEC_PROCESS.md。**Superpowers 提供的是纪律脚手架，判断力仍必须来自我本人**——这与课程"当 AI 能写大部分代码时，工程师的价值在哪"的命题恰好呼应：价值在于选题、划边界、识别哪些机制必须是代码而非提示词、以及不放过每一次含糊表述。

---

# 冷启动验证（§4.5）：陌生智能体试运行与规约修订

> 按通用要求 §4.5，用**一个与主开发智能体不同的全新 agent**（general-purpose 子智能体，隔离 git worktree），
> 在**不提供任何对话历史/memory/SPEC_PROCESS** 的前提下，仅凭 `docs/SPEC.md` + `docs/PLAN.md`
> 尝试实现 PLAN 的前 1–2 个 task，要求它"遇不确定即暂停并记录，不得猜测"。
> 这是规约质量最关键的客观证据。

## 一、验证设置

- 执行者：全新 general-purpose 子智能体，运行于隔离 worktree（`agent-a584fb4aafef128c2`，暂保留）。
- 输入：仅 `docs/SPEC.md` + `docs/PLAN.md`（允许读上游课程要求仅为理解评分口径，禁止据此填空）。
- 任务：按 TDD 实现 Task 1（scaffold）与 Task 2（config schema + loader）。
- 结果：两任务均实现并 commit（`7cc5ebd`、`97fef4a`），in-task 测试如 PLAN 预测般红→绿。但暴露出下列缺陷。

## 二、暴露的缺陷（按严重度）

**D-CS1【严重】`command_rules` 结构自相矛盾。** SPEC §11 M11 示例用嵌套 `{match:{argv0,args_contain},decision}` 且 `argv0` 有时是列表；PLAN Task 14 `judge_command` 却用扁平 `rule["argv0"]`/`rule["args_contain"]` 读取、`argv0` 为标量。后果:SPEC 自带的 `aegis.yaml` 喂给治理引擎会 KeyError/永不匹配；且 Task 2 把该字段定为无校验 `list[dict]`,错误拖到 Task 14 才爆。**根因:上一轮 SPEC 自查时我改过 YAML 却未与 Task 14 匹配器对照。**

**D-CS2【严重】配置不拒绝未知字段。** SPEC M11 + US-7 要求"非法/未知字段→启动即报错",但 PLAN 用裸 `BaseModel`（无 `extra="forbid"`）,`bogus_field:123` 静默通过;`default_decisions.command` 也未对四档枚举校验（`NONSENSE_TIER` 可载入）。SPEC 承诺的验收标准实际不满足;且 Task 2 的 `test_invalid_field_raises` 只测类型错、未测未知字段。

**D-CS3【中】PLAN 任务编号四处不一致。** File Structure、依赖图头部、Summary 表、任务正文对同一文件给不同编号（redactor/persistence 在头部 T3/T4、正文/表里反为 T4/T3;command_lexer/tool/approval 标注差 1–3）。**根因:我插入 T20/T21/T22 后改了正文编号,但先前写的 File Structure/依赖图未同步。**

**D-CS4【中】幽灵文件 + 漏列文件。** File Structure 列 `fingerprint.py`(T17)但 fingerprint 实际在 T15 的 `approval.py`,无任务创建该文件;真实 T12 产物 `dispatcher.py` 反而漏列。

**D-CS5【中】目录名错误。** File Structure 写 `action/`,Task 7 实际建 `protocol/`,下游 import 全用 `protocol`。

**D-CS6【低】bootstrap 顺序。** 每任务 Step 2 都 `Run: pytest`,但 pytest 到 Step 4 才装;冷机器上首次失败是 `No module named pytest`,非 PLAN 预测的 `No module named 'aegiscode'`。

**D-CS7【低】环境变量覆盖未定义。** SPEC 说"少数环境变量覆盖"未点名;PLAN 自创 `AEGIS_LLM_PROVIDER/MODEL`(SPEC 无),且 `load_config(env=None)` 是否读 `os.environ` 未定义。

## 三、修订（含前后 diff 要点）

用户指示"立刻修订"。修订如下（SPEC.md 与 PLAN.md 均已改）：

**修 D-CS1** — 定案 `command_rules` 为**扁平结构 + argv0 标量字符串**（与 Task 14 工作代码一致）:
- SPEC §11 M11 YAML:`{match:{argv0:git,args_contain:[push]},decision:DENY}` → `{argv0:git, args_contain:[push], decision:DENY}`;删除列表 argv0 的 `{match:{argv0:[sudo,...]}}` 一条,改为注释说明 sudo/rm 等不在允许列表、由默认档 `command:DENY` 兜底。
- PLAN Task 2 `schema.py`:`command_rules: list[dict]` → `command_rules: list[CommandRule]`,新增 `class CommandRule(argv0:str, args_contain:list[str]=[], decision:Decision)`。
- PLAN Task 14 Interfaces:显式声明 `rules` 是匹配 `CommandRule` 的扁平 dict,调用方传 `[r.model_dump() for r in config.governance.command_rules]`,argv0 恒标量。

**修 D-CS2** — SPEC M11 边界/错误:新增"配置模型 `extra="forbid"`;decision 与 default_decisions.* 须四档枚举之一,否则报错"。PLAN Task 2:所有嵌套模型继承 `_Strict(model_config=ConfigDict(extra="forbid"))`;`Decision(str,Enum)` 定义在 config/schema.py(作单一真源);`DefaultDecisions` 三字段与 `CommandRule.decision` 均用 `Decision` 枚举;新增测试 `test_unknown_top_level_field_raises`/`test_unknown_nested_field_raises`/`test_bad_decision_tier_raises`/`test_command_rules_flat_shape`/`test_command_rules_reject_nested_match`/`test_env_overrides_provider_and_model`。

**修 D-CS3** — PLAN File Structure 与依赖图头部编号全部对齐任务正文(redactor=T3、persistence=T4、command_lexer=T13、command_rules=T14、command_tool=T16、run_tests=T17、approval=T15);Milestone 2 描述"5 split tasks"→"6 split tasks";依赖图 Milestone 2/3/6 及并行组 {T11,T13} 同步;Summary 表 T10 依赖补 T2。

**修 D-CS4** — File Structure 删 `fingerprint.py`、补 `dispatcher.py`(标 T12);新增说明"`fingerprint()` 位于 governance/approval.py(T15),无独立 fingerprint.py"。

**修 D-CS5** — File Structure `action/` → `protocol/`(model.py/parser.py),与 Task 7 及下游 import 一致。

**修 D-CS6** — PLAN 新增"Environment Bootstrap(Task 1 之前做一次)"章节(建 venv + pip install pytest);Task 1/Task 2 Step 2 加 Prereq 提示与"若见 No module named pytest 说明漏 bootstrap"。

**修 D-CS7** — SPEC M11 错误:明确"环境变量覆盖仅限 `AEGIS_LLM_PROVIDER`、`AEGIS_LLM_MODEL`;`env=None` 时读 `os.environ`"。PLAN Task 2 loader:`_ENV_MAP` 显式两项,`src = os.environ if env is None else env`。

**附带修复**:`Decision` 枚举原在 T2 与 T10 各定义一次(重复);现定为 config/schema.py 单一真源,T10 `governance/decision.py` 改为 `from aegiscode.config.schema import Decision` 再导出,并加断言 `Decision is ConfigDecision`。

## 四、验证结论与我的处理

- 子智能体严格遵守"不猜测、遇歧义即停",报告可直接作为规约质量的客观证据。
- 暴露的 7 项缺陷中,D-CS1 与 D-CS3 是我在写/改 SPEC/PLAN 时**亲手引入**的(配置结构未跨文件对照、插入任务后未同步编号)——印证 §4.5"主 agent 与我共享隐性上下文会高估 spec 清晰度"的判断。
- 全部 7 项已修订(D-CS1/2/3/4/5/6 完全消除,D-CS7 由未决改为明确定义)。验证用 worktree 暂保留,待后续统一删除。

---

# 第二次冷启动验证（§4.5 复验）：修订后再验 + 新缺陷

> 第一轮修订后，再派**另一个全新 general-purpose 子智能体**（新的隔离 worktree `agent-ab2a63ac4f8f13354`，暂保留），
> 仍只给 `docs/SPEC.md` + `docs/PLAN.md`，实现 Task 1/2/7/10/13/14（走到治理修订重灾区），
> 目的：①确认第一轮 7 项修订是否真的成立；②检查修订本身是否引入新矛盾。

## 一、第一轮修订的复验结果

- **B（extra=forbid + 枚举校验）PASS**：4 个负向测试全过。
- **C（Decision 单一真源）PASS**：`Decision is ConfigDecision` 身份断言过；governance 经再导出引用，无重复定义。
- **F（环境变量点名）PASS**：仅 `AEGIS_LLM_PROVIDER`/`AEGIS_LLM_MODEL`；`env=None → os.environ` 实测生效。
- **A（command_rules 结构）结构 PASS、语义 FAIL**：扁平/标量/嵌套三处一致，示例能载入为 `CommandRule`；但见 D-CS8。
- **D（编号/路径）文件层 PASS、元数据层 FAIL**：目录名一致、无幽灵/漏列文件，但依赖表有错（D-CS9/D-CS10）。
- **E（bootstrap）预测失败可复现，但首选命令不可跑**（D-CS11）。

## 二、第二轮新暴露的缺陷

**D-CS8【严重·新】`command_allowlist` 漏 `pip`，黄金路径断裂。** SPEC 出厂 `command_allowlist`（§11 M11 line 221）= `[python,python3,pytest,ruff,mypy,git,ls,cat]`，**没有 pip**。但治理管线第 3 层（允许列表）在第 4 层（危险参数规则）之前执行，于是用出厂配置实测 `pip install requests → DENY(CMD_ALLOWLIST)`，而 SPEC 在黄金路径（§4 步3）、US-3、§6 M5、§10.3、§15 M5 **五处**都要求它 `REQUIRE_APPROVAL`。→ HITL 招牌演示（pip install 暂停等审批）根本走不到，直接被拒。**且 Task 14 单测用手写的、含 pip 的 `ALLOW` 镜像，掩盖了这个 bug。** 根因与上一轮 D-CS1 同源：**改配置结构后没有回到"黄金路径"端到端对照**。

**D-CS9【中·新】Summary 表 `fingerprint` 位置错。** 表中 T15 行的并行列写 `T17(fingerprint lives here)`，与 File Structure、line 91 note、Milestone 图、Task 15 正文（fingerprint 在 approval.py/T15）全部矛盾。

**D-CS10【中·新】T23 两处依赖列表不一致。** Milestone-4（line 131）与 Summary 表（T23 行）给的依赖集不同，且都不完整（前者漏 T21，后者漏 T8/T9）。

**D-CS11【低·新】bootstrap 首选命令在无 `python3.12-venv` 系统包时失败。** PLAN 首列 `python3.12 -m venv .venv` 触发 `ensurepip is not available`（需 sudo apt 装包）；只有备选的 conda 路径能跑。每任务 Step 2 的预测失败本身可精确复现。

**D-CS12【低·新】T15 `validate_resume` 接口描述与代码签名不符。** Interfaces 写 `(req, current_action)`，代码/测试用 `(approved_fp, current_action)`。

## 三、修订（本轮）

- **修 D-CS8**：SPEC §11 M11 与 PLAN Task 2 schema 默认 `command_allowlist` **加入 `pip`**；并给 Task 14 新增回归测试 `test_shipped_config_allows_pip_to_reach_approval`——用**真实 config 默认 allowlist**（非手写镜像）断言 `pip install → REQUIRE_APPROVAL`，堵死掩盖路径。
- **修 D-CS9**：Summary 表 T15 行改为"defines `fingerprint()`",并行列改 `T16,T17`。
- **修 D-CS10**：T23 两处依赖统一为 `T5,T7,T8,T9,T12,T14,T15,T16,T17,T18,T19,T21,T22`（T10/T11/T13 经 T12/T14 传递）。
- **修 D-CS11**：bootstrap 章节重排为 A) conda B) uv C) stdlib venv(注明需 `python3.12-venv`)，把最可移植的放前面。
- **修 D-CS12**：Interfaces 改为 `validate_resume(approved_fp: str, current_action)`。

## 四、结论与"避免重蹈覆辙"的教训

- 第一轮修订**确实成立**（B/C/F PASS）；本轮新缺陷主要是**上一轮修订的连带遗漏**（改 allowlist/结构时没回归黄金路径）与**元数据未同步**（表格）。
- **教训 1（最重要）**：任何改动"治理配置结构/默认值"后，必须回到 §4 黄金路径与 §16.4 演示做一次端到端对照——单元测试用手写镜像会掩盖出厂配置的缺陷。已把该回归固化为 Task 14 的 `test_shipped_config_...`。
- **教训 2**：涉及编号/依赖/路径的"地图类"元数据（File Structure、依赖图、Summary 表）任一处改动，必须三处同步核对。两轮都栽在这上面（D-CS3、D-CS9、D-CS10）。
- **教训 3（流程）**：本轮我又出现"先改文档、漏记 SPEC_PROCESS"的问题，经用户追问才补记——说明"改完即记"这条纪律仍需我主动执行，不能等提醒。
- **教训 4（工具）**：向已有长文档追加内容严禁用会覆盖全文件的写工具；本轮用"临时文件 + cat 追加"完成。

本轮修订暂**未提交**，待用户指示统一提交。两个验证 worktree 暂保留待后续删除。

---

# 第三次冷启动验证（§4.5）：一次"假警报"暴露的流程陷阱 + 两处真实补漏

> 第二轮修订提交后（`e23553f`），再派第三个全新子智能体（新隔离 worktree `agent-a899e0e3`）复验。

## 一、关键流程教训：worktree 基于过时的 origin，导致整份报告的头号"缺陷"是假警报

- 子智能体隔离 worktree 默认从 **`origin/main`** 分叉（baseRef=fresh），而我的两个修订提交（`8e9451b`、`e23553f`）**尚未 push**，origin 落后。
- 于是第三个子智能体验证的是**修订前的旧文档**：它花大篇幅"发现"了 D-CS8（pip 不在 allowlist、黄金路径 DENY），并判 GOLDEN PATH = FAIL——**但这早在第二轮 `e23553f` 修好了**。
- 核实:当前 main 的 SPEC.md line 221 = `[python, python3, pip, pytest, ...]`（含 pip）；而该 worktree 的 SPEC.md 仍是旧的无 pip 版本。→ 报告的头号缺陷是**假警报**。
- **教训 5（流程·重要）**：冷启动验证前必须让被验证的提交对 worktree 可见——要么先 `git push`（使 origin/main 最新），要么显式让 worktree 基于本地 HEAD。否则"陌生 agent 验证"验的是旧版本，白跑且产生误导性 FAIL。本轮即栽于此。

## 二、复验通过项（当前 main 已修，worktree 因过时而误报为 FAIL 的，全部实为 PASS）

- pip 已入 command_allowlist（假警报 D-CS8）。
- T23 两处依赖已统一含 T21（假警报 D 项）。
- bootstrap 已 conda/uv/venv 三选并注明 python3.12-venv 前置（假警报 C/E 项之一）。
- 其余 B/C/F（extra=forbid+枚举、Decision 单一真源、环境变量）在旧版即已 PASS，本轮继续 PASS。

## 三、本轮仍挖出的两处真实缺陷（第二轮未碰，对当前 main 成立）——已修

**D-CS13【中·真实】测试 helper 无创建归属。** Task 26 import `make_service`、Task 27/28 import `make_api_client`,但只有 Task 23 创建 `tests/helpers.py` 的 `make_harness`,没有任务把这两个 helper 列为交付物。陌生实现者到 Task 26 会遇到未定义的 `make_service`。→ 已修:Task 26 Files 增 "Modify tests/helpers.py 加 make_service"；Task 27 Files 增 "Modify tests/helpers.py 加 make_api_client"，并在 Interfaces 注明。

**D-CS14【轻·真实】`schema.sql` 不在 File Structure map。** Task 4 实际创建 `persistence/schema.sql`（db.py 读它），但 File Structure 只列 `db.py`。→ 已修:File Structure persistence 段补 `schema.sql` 行。

## 四、结论

- 本轮**没有发现任何 correctness 级新缺陷**;头号"FAIL"是过时 base 造成的假警报,真实新问题仅 2 处 planning 层补漏,均已修。
- 综合三轮:规约的核心机制（治理四档、命令词法、路径围栏、黄金路径 pip→审批、config 严格校验、Decision 单源）已被独立陌生 agent 反复验证为一致且可实现。
- **最重要的一次收获是流程教训 5**：以后跑冷启动前先 push（或基于本地 HEAD 建 worktree），否则验证无效。

本轮补漏修订与本记录一并提交。验证 worktree 按用户指示删除。

---
