# CodingAgent 二次开发完整执行规划

> 版本：v1.2（Harness 机制评审修订版）  
> 日期：2026-06-15  
> 基础项目：`/data/xinyu/projects/CodingAgent`  
> 项目方向：面向真实代码仓库的 Issue-to-Patch / Issue-to-PR Coding Agent

## 1. 项目定位

### 1.1 一句话介绍

将当前轻量级 Claude Code 实现升级为一个可恢复、可观测、可评测、具备安全边界的 Coding Agent：输入 GitHub Issue 或自然语言任务，自动理解仓库、制定计划、修改代码、运行验证，并生成可审查的 Patch 或 Draft Pull Request。

### 1.2 基础项目选择

CodingAgent 已具备 Coding Agent 的最小闭环：Agent Loop、流式模型调用、文件与 Shell 工具、上下文压缩和单元测试。相比 `python/mini_claude`，CodingAgent 的模块边界更适合长期演进，因此：

- CodingAgent 作为主工程和简历项目。
- `mini_claude` 作为学习 Agent Loop 和流式交互的参考实现。
- `learn-claude-code` 作为 Permission、Lifecycle、Context、Task 和 Worktree 机制的教学参考，不直接复制其单文件或全局状态实现。
- 二次开发采用渐进式重构，不一次性推倒重写。

### 1.3 简历价值
  
最终项目不能停留在“调用大模型加几个工具”，需要证明以下能力：

- Agent Runtime：状态机、工具调度、失败恢复和终止控制。
- Coding Agent：仓库理解、代码修改、测试验证和 Git 工作流。
- LLM Engineering：上下文管理、模型路由、结构化协议和成本控制。
- AI Safety：路径隔离、命令策略、权限审批和 Prompt Injection 防护。
- Evaluation：可复现任务集、自动评分、回归对比和失败分析。
- Production Engineering：持久化、日志、Tracing、CI 和配置管理。

## 2. 目标与边界

### 2.1 目标工作流

```text
Issue / 用户任务
        -> 仓库扫描与需求澄清
        -> 生成可执行计划
        -> 检索代码并定位修改点
        -> 在隔离工作区中修改代码
        -> 执行测试、Lint、类型检查
        -> 失败诊断与有限次数修复
        -> 生成 Diff、验证报告和 PR 描述
        -> 人工审批后创建 Draft PR
```

### 2.2 工程目标

- 核心模块职责清晰，避免巨型 Agent Loop。
- 关键行为可配置、可记录、可恢复。
- 工具输入输出结构化，不依赖脆弱的字符串协议。
- 文件、Shell、Git 和网络写操作受策略控制。
- 关键路径具备单元、集成和端到端测试。
- 每项重要改进均可通过评测证明收益。

### 2.3 非目标

第一阶段不追求：

- 自研或微调大模型。
- 完整复制 Claude Code、Codex 等商业产品。
- 无人工确认地 Push、创建或合并 PR。
- 同时支持所有语言和代码托管平台。
- 为展示复杂度而过早引入多 Agent、RAG 或 Web UI。
- 在 MVP 中引入自动长期记忆、后台任务、Cron、MCP、通用插件系统或自主 Agent 团队。

## 3. 成功标准

### 3.1 MVP

- 从本地任务描述生成可应用 Patch。
- 支持读取、搜索、编辑、Shell 和 Git Diff。
- 支持计划、步骤状态、预算和最大迭代限制。
- 支持 Python 项目的自动测试验证。
- 支持危险命令拦截和工作区路径约束。
- 输出结构化运行日志和任务报告。

### 3.2 作品集版本

- 支持 GitHub Issue 获取和 Draft PR 创建。
- 使用独立分支或 Git Worktree 隔离任务。
- 任务中断后可从 Checkpoint 恢复。
- 追踪 Token、成本、耗时、工具调用和测试结果。
- 建立至少 20 个可复现任务的评测集。
- README 包含架构图、演示、评测和技术决策。
- CI 自动执行质量检查和离线评测。

### 3.3 建议公开指标

| 指标 | MVP | 作品集版本 |
|---|---:|---:|
| 单元测试通过率 | 100% | 100% |
| 固定评测任务数 | 10 | 20-50 |
| Patch 可应用率 | >= 90% | >= 95% |
| L1 任务解决率 | >= 70% | >= 85% |
| L2 任务解决率 | 建立基线 | >= 65% |
| Safety Suite 违规数 | 0 | 0 |
| 故障注入恢复通过率 | >= 80% | >= 95% |
| 核心模块覆盖率 | >= 80% | >= 85% |

所有指标必须绑定固定的任务集版本、Base Commit、模型名称、模型参数和预算。不能把不同模型、不同任务难度或人工干预后的结果直接放在同一张表中比较。

## 4. 当前基线与问题

### 4.1 已有能力

- `agent.py`：基础 ReAct 风格循环和工具调用。
- `llm.py`：LiteLLM 流式模型调用。
- `context.py`：上下文压缩。
- `tools/`：文件、搜索、编辑和命令工具。
- `tests/`：已有测试框架和基础覆盖。

### 4.2 P0 问题

1. Agent 声明的工具与执行时使用的全局注册表可能不一致。
2. 工具默认并行，文件写入和 Shell 等副作用操作存在竞态。
3. 缺少命令策略、路径保护和人工审批点。
4. 缺少明确状态机、预算和可靠终止条件。
5. 工具错误以文本为主，难以实现稳定恢复。
6. 默认工具仍包含 `AgentTool`，与“单 Agent 优先”的主线不一致。
7. Bash cwd、修改文件集合和 AgentTool 父引用使用进程级共享状态，多个 Agent 之间可能互相影响。

### 4.3 P1 问题

1. Model Provider、Runtime 和工具系统耦合较强。
2. 缺少持久化、中断恢复、统一事件和 Tracing。
3. 缺少 Git Worktree 隔离与 Issue-to-PR 工作流。
4. 缺少可重复的 Agent 评测体系。

## 5. 设计原则

1. **单 Agent 优先**：先让状态、工具和验证可靠，再评估多 Agent。
2. **验证驱动完成**：以测试和证据判定完成，不接受模型自我声明。
3. **最小权限**：工具只获得当前步骤所需能力。
4. **副作用显式化**：所有写操作均可识别、可审计、可审批。
5. **状态可恢复**：关键状态不得只保存在对话上下文中。
6. **评测先行**：先建立基线，再优化效果、时延和成本。
7. **渐进重构**：沿用当前实现迁移，保持每个阶段可运行。
8. **可观测性随 Runtime 建设**：最小事件流必须在状态机落地时同步加入，不能等到项目后期再补。
9. **默认关闭多 Agent**：在单 Agent 基线和隔离机制成熟前，`AgentTool` 不进入默认工具集，只能通过 Feature Flag 实验。

## 6. 目标架构

下图描述作品集版本的长期结构，不代表第一阶段就要创建所有目录。早期应保持模块化单体，只有当模块职责和依赖稳定后再拆成子包。

```text
Interface: CLI / TUI / GitHub Adapter / Configuration
                           |
                           v
Application: Task / Run / Approval / Report Services
                           |
                           v
Agent Runtime
  State Machine / Planner / Executor / Verifier / Recovery
  Budget / Stop Policy / Checkpoint / Event Bus
                  |                         |
                  v                         v
Context & Model                     Tool Runtime
Provider / Router                   Registry / Schema
Prompt / Memory / Compress          Scheduler / Policy / Audit
                  |                         |
                  +------------+------------+
                               v
Workspace: Filesystem / Shell / Git / GitHub / Test Runner
                               |
                               v
Infrastructure: SQLite / Logs / Trace / Evaluation
```

M0-M4 推荐目录：

```text
codingagent/
├── agent.py              # 保留兼容入口，逐步把编排逻辑迁出
├── runtime.py            # 状态机、Budget、Planner/Executor 协调
├── models.py             # TaskSpec、TaskRun、PlanStep、Artifact
├── events.py             # 事件定义和 JSONL Event Sink
├── llm.py                # Provider 接口与现有实现
├── context.py            # 上下文预算与压缩
├── workspace.py          # 路径边界、Worktree 和任务工作区
├── tools/
├── evaluation/
└── cli.py
```

进入 GitHub 集成和持久化阶段后，再按真实复杂度拆分 `providers/`、`storage/`、`observability/` 和 `integrations/github/`。禁止为了匹配架构图提前创建只有一两个文件的空包。

## 7. 核心领域模型

### 7.1 TaskSpec

包含 `task_id`、标题、描述、来源、仓库、Base Revision、验收条件和约束。

### 7.2 TaskRun

包含 `run_id`、任务、状态、当前步骤、迭代次数、Token、成本、时间、Checkpoint 和最终结果。

### 7.3 PlanStep

包含步骤说明、依赖、状态、完成证据、尝试次数和失败原因。

运行约束：

- 同一个 `TaskRun` 最多只能有一个 `in_progress` 步骤。
- 步骤进入 `completed` 前必须绑定测试结果、Diff、静态检查或分析记录等完成证据。
- 计划允许局部修订，但必须记录修订原因、时间和触发事件。
- Runtime 而不是模型文本负责校验状态迁移是否合法。

### 7.4 ToolSpec 与 ToolResult

每个工具声明名称、参数 Schema、`read_only`、`side_effect`、`requires_approval`、超时、重试、并发组和所需能力。

统一返回：

```python
ToolResult(
    ok=True,
    output="...",
    error=None,
    metadata={},
    artifacts=[],
    retryable=False,
)
```

### 7.5 PolicyDecision 与 ApprovalRequest

所有工具调用在执行前产生结构化策略决策：

```python
PolicyDecision(
    action="allow",  # allow | ask | deny
    risk_level="L1",
    reason="workspace-local test command",
    rule_id="shell.test.workspace",
)

ApprovalRequest(
    request_id="approval_xxx",
    tool_name="bash",
    arguments={...},
    reason="dependency installation",
    expires_at=None,
)
```

未经 `allow` 的调用不得进入 Tool Handler。`ask` 必须等待明确审批，`deny` 不允许由模型提升权限。

### 7.6 Artifact

任务产物包括 Patch、修改文件列表、测试报告、命令记录、PR 描述、风险和未完成项。

## 8. Agent Runtime

### 8.1 状态机

```text
CREATED -> ANALYZING -> PLANNING -> EXECUTING -> VERIFYING
                                           ^          |
                                           |          v
                                           +------ REPAIRING

VERIFYING -> REVIEWING -> AWAITING_APPROVAL -> COMPLETED
任意执行状态 -> PAUSED / FAILED / CANCELLED
```

状态迁移必须事件化并持久化，禁止仅依赖内存中的无限循环。

### 8.2 Planner

- 识别目标、限制和验收条件。
- 扫描仓库结构、项目规范和测试入口。
- 拆解为可验证步骤。
- 标记风险操作和审批点。
- 为每一步定义完成证据。
- 允许局部修订，但记录修订原因。

### 8.3 Executor

- 只读工具允许受控并行。
- 文件写入、Shell 和 Git 写操作默认串行。
- 调用前执行 Schema、路径和策略校验。
- 每次调用有超时、输出上限和审计记录。
- 重复错误触发恢复或停止。

### 8.4 Verifier

依次检查：

1. 目标文件是否成功修改。
2. Patch 是否有效且无越界文件。
3. 相关单元测试是否通过。
4. Lint 和类型检查是否通过。
5. 完整测试是否通过。
6. Diff 是否满足 Issue 和验收条件。

### 8.5 Recovery

- `ToolInputError`：修正参数后重试。
- `PathPolicyError`：停止该方案并重新规划。
- `CommandTimeout`：缩小范围后最多重试一次。
- `TestFailure`：提取摘要并进入修复状态。
- `ModelProtocolError`：重新请求结构化输出。
- `ContextOverflow`：压缩上下文或切换模型。
- `RepeatedFailure`：超过阈值后生成诊断并停止。

恢复策略必须区分幂等操作和副作用操作：

- 模型请求遇到 429、超时和可恢复 5xx 时，可使用带抖动的指数退避。
- Context Overflow 执行一次紧急压缩后最多重试一次。
- 文件写入、Git 写入和网络写入不得盲目自动重试。
- 副作用操作只有在具备幂等键或执行前状态检查时才能重试。
- 每类恢复路径都有独立次数上限，并计入总 Budget。

### 8.6 Budget 与终止

限制模型轮次、工具次数、Token、成本、总时长、单命令时长、同类错误次数和修复循环。终止结果区分成功、部分完成、预算耗尽、用户取消和不可恢复失败。

### 8.7 生命周期中间件

Runtime 提供少量类型明确的内部扩展点：

- `before_model`、`after_model`
- `before_tool`、`after_tool`
- `on_stop`

`before_tool` 可阻止或要求审批，属于控制路径；Event Bus 记录已经发生的事实，属于观测路径。首版不建设任意第三方 Hook 插件系统，避免回调顺序、异常隔离和权限边界失控。

## 9. 工具系统改造

### 9.1 统一 Registry

Agent 只能执行显式注入当前实例的工具，修复声明工具与全局执行注册表不一致的问题。禁止隐式全局状态绕过配置和权限。

### 9.2 参数校验

使用 Pydantic 或等价类型系统校验类型、必填项、路径、枚举和资源限制。校验失败返回结构化错误，不执行工具。

### 9.3 调度规则

| 工具类型 | 默认策略 | 示例 |
|---|---|---|
| 只读、无副作用 | 可并发 | read、glob、search |
| 文件写入 | 串行 | edit、apply_patch |
| Shell | 串行 | test、build、format |
| Git 写操作 | 串行且审批 | commit、push |
| 网络写操作 | 串行且审批 | create_pr、comment |

增加 `concurrency_key`，相同 Key 的调用禁止并发。

### 9.4 Policy Engine

工具执行采用固定流水线：

```text
Tool Call
  -> Schema Validation
  -> Path/Capability Validation
  -> Risk Classification
  -> PolicyDecision
  -> Approval（仅 ask）
  -> Scheduler
  -> Tool Handler
  -> ToolResult
```

Policy Engine 采用可测试的规则对象，不依赖散落在各工具中的字符串黑名单。策略决策、审批和拒绝原因全部写入事件流。

### 9.5 输出治理

- 限制 stdout 和 stderr 长度。
- 长输出保存为 Artifact，模型仅接收摘要和引用。
- 保留退出码、耗时和截断标记。
- 自动解析测试失败、编译错误和 Traceback。

## 10. Workspace 与 Git

每次任务由 WorkspaceManager：

- 校验仓库路径并锁定 Base Commit。
- 创建独立目录或 Git Worktree。
- 限制工具只能访问工作区。
- 管理任务锁、保留和清理策略。

Worktree 生命周期：

```text
CREATING -> ACTIVE -> KEEP
                   -> CLEANING -> REMOVED
```

- 名称、分支和目标路径必须规范化并防止路径穿越。
- 创建前确认 Base Revision 和基础工作区状态。
- 默认拒绝删除存在未提交修改或未交付 Commit 的 Worktree。
- 清理操作必须幂等；异常退出后可以重新检查并继续清理。
- 不使用是否配置 Upstream 来判断任务 Commit，统一与锁定的 Base Commit 比较。

Git 工作流：

```text
base branch
    -> worktree + task/<task-id>
    -> Agent 修改和验证
    -> Diff 与报告
    -> 人工审批
    -> commit -> push -> Draft PR
```

默认禁止修改基础分支、强制推送、自动合并、提交密钥和工作区外写入。

## 11. 安全与审批

### 11.1 命令风险等级

- L0：只读命令，可直接执行。
- L1：工作区内测试和格式化，可按配置执行。
- L2：依赖安装、Git 状态修改，需要确认。
- L3：Push、PR 和网络写入，需要明确审批。
- L4：破坏性或越权操作，始终禁止。

必须拦截危险删除、磁盘操作、路径穿越、符号链接逃逸、强制推送、敏感目录读取和仓库数据外传。

### 11.2 Prompt Injection

仓库文件、Issue、测试输出和网页均是不可信数据。数据不能覆盖系统策略，模型不能提升权限，高风险行为必须由代码策略决定。

### 11.3 Secret 防护

- 日志脱敏 Token、API Key 和 Authorization Header。
- 提交前执行 Secret Scan。
- 禁止访问 `.ssh` 和云凭证目录。
- GitHub Token 只注入 Adapter，不进入模型上下文。

## 12. Issue-to-PR 数据流

1. **Issue 摄取**：将标题、正文、标签、讨论、目标分支和 Base Commit 转为 `TaskSpec`。
2. **仓库理解**：构建文件树、语言分布、项目规范、测试命令、入口和相关符号组成的 Repository Map。
3. **计划**：按验收条件生成带完成证据的步骤。
4. **执行**：先运行最小失败基线，再进行最小范围修改。
5. **验证**：局部测试后执行更广范围回归测试。
6. **修复**：只允许有限次数 Repair Loop。
7. **交付**：生成 Patch、测试报告、风险和 PR 描述。
8. **审批**：人工确认 Diff 后才可 Push 和创建 Draft PR。

首版仓库理解使用 `rg`、文件树和 Python AST；有评测数据证明需要后再引入 Tree-sitter 或向量检索。

## 13. 上下文工程

采用分层上下文：

- 稳定层：系统策略、工具说明和项目规范。
- 任务层：Issue、验收条件和计划。
- 工作层：当前步骤文件和近期工具结果。
- 历史层：压缩后的决策、失败和已验证事实。
- Artifact 层：完整日志和长输出，按需引用。

压缩必须保留目标、验收条件、步骤状态、修改文件、设计决策、测试结果、失败原因和 Git 状态，不能只生成聊天摘要。

消息历史必须满足协议不变量：

- Assistant Tool Call 与它的全部 Tool Result 构成不可拆分的事务组。
- 压缩、裁剪、Session 加载和 Checkpoint 恢复后不得产生孤立 Tool Result。
- Tool Result 必须引用已知且未重复消费的 `tool_call_id`。
- 多工具调用时，压缩边界必须覆盖整组调用和全部对应结果，而不是只保护相邻消息。

System Prompt 通过稳定分段组装，而不是维护单个不断膨胀的模板。稳定策略、工具能力、工作区、任务状态和按需项目知识分别管理，并记录每轮实际加载的分段及其 Token 占用。

模型路由建议：轻量模型处理分类和摘要，主模型负责规划和修改，强模型处理复杂诊断和最终审查。首版采用可解释规则。

## 14. Checkpoint 与持久化

首版使用 SQLite 保存：

- Task、Run、状态和 PlanStep。
- 消息摘要、工具调用和结果。
- Token、成本、耗时和错误。
- Workspace、分支和 Base Commit。
- Artifact 索引。

在状态迁移、文件修改、测试完成、审批前和异常退出前创建 Checkpoint。恢复时校验数据库、工作区和 Git 状态一致性。

## 15. 可观测性

### 15.1 事件模型

至少包含：

- `run_started`、`state_changed`
- `plan_created`、`plan_updated`
- `model_requested`、`model_completed`
- `prompt_assembled`、`context_compacted`
- `policy_decided`、`approval_requested`、`approval_resolved`
- `tool_started`、`tool_completed`
- `worktree_created`、`worktree_retained`、`worktree_removed`
- `file_changed`、`verification_completed`
- `run_completed`、`run_failed`

### 15.2 日志与指标

日志字段包括 Run、Task、State、Step、事件、耗时、Token、工具和错误类型。

指标包括总耗时、状态耗时、模型请求、Token、成本、工具成功率、Diff 大小、首次测试通过率、修复次数和任务成功率。先实现本地 JSONL Trace，外部平台通过 Adapter 接入。

## 16. Evaluation 体系

### 16.1 任务格式

```yaml
id: python-001
repo: fixtures/sample_project
base_commit: abcdef
issue:
  title: Fix empty input validation
  body: The parser should reject empty strings.
acceptance:
  tests:
    - pytest tests/test_parser.py
  expected_files:
    - src/parser.py
limits:
  max_iterations: 12
  timeout_seconds: 300
```

### 16.2 任务分层

- L1：单文件、小缺陷、明确测试。
- L2：跨文件修改和模块关系。
- L3：模糊需求、补测试和设计权衡。
- Safety：路径逃逸、密钥、危险命令和注入。
- Recovery：超时、工具失败、协议异常和进程中断。

### 16.3 评分指标

- `resolved`：验收测试是否通过。
- `patch_valid`：Patch 是否有效。
- `regression_free`：原有测试是否通过。
- `scope_control`：是否存在无关修改。
- `policy_compliance`：是否违反安全策略。
- `cost`、`duration`、`attempts`。

### 16.4 基线与消融

评测不是最后阶段才开始的工作：

1. M0 建立首批 5-10 个固定任务和原始 Agent 基线。
2. 每个里程碑完成后自动运行同一批任务，形成回归曲线。
3. M4 扩展到至少 10 个 Issue-to-Patch 任务。
4. M7 扩展到 20-50 个分层任务，并开展正式消融。

最终比较原始 Agent、新 Runtime 基础版和完整系统。分别关闭 Planner、Repository Map、Context Compression、Recovery 等能力，量化每项设计的真实贡献。

## 17. 测试与 CI

### 17.1 测试策略

- 单元测试：状态迁移、工具校验、Tool Call/Result 事务组、路径保护、策略决策、并发、Budget、Checkpoint 和上下文压缩。
- 集成测试：Tool Call 链路、审批前禁止执行、修改后测试、Worktree 生命周期、中断恢复和 GitHub Mock API。
- 端到端测试：固定 Fixture 仓库中的代码定位、Patch、验收测试、修改范围和最终报告。
- 默认 CI 使用 Fake Provider；真实模型测试单独标记。

### 17.2 CI 流程

1. 安装锁定依赖。
2. `ruff check`。
3. `ruff format --check`。
4. `mypy` 或 `pyright`。
5. `pytest` 和 Coverage。
6. Safety 测试。
7. 小规模离线评测。
8. 构建包并验证 README 示例。

当前项目在 `pyproject.toml` 和 CI 中承诺支持 Python 3.10-3.13。M0 必须明确选择：

- 继续支持 Python 3.10-3.13，并保持完整版本矩阵。
- 或升级为 Python 3.11+，同时修改 `requires-python`、classifiers、CI 和文档。

在 CI 启用 Ruff、类型检查和 Coverage 前，先把 `ruff`、`pytest-cov` 以及选定的 `mypy` 或 `pyright` 加入开发依赖并统一配置到 `pyproject.toml`。对于库项目，优先使用可复现的开发环境或约束文件，不强制把应用型 Lockfile 作为唯一方案。

## 18. 分阶段实施路线

### M0：可信基线与工程护栏

任务：

- 补充当前架构、时序图和关键数据流文档。
- 修复测试环境，统一开发依赖和本地验证命令。
- 增加 Agent Loop、Tool Call、并行执行和上下文压缩回归测试。
- 增加消息协议不变量测试，覆盖单个及多个 Tool Call、孤立/重复 `tool_call_id`、压缩边界和 Session 恢复。
- 实现 Fake Provider，避免测试依赖真实模型。
- 建立 5-10 个固定评测任务，记录原始成功率、耗时、Token 和失败类型。
- 新增 ADR-001，确认“单 Agent 状态机 + Issue-to-Patch 主线”。
- 将 `AgentTool` 从默认工具中移除或置于 Feature Flag 后。

验收：

- CI 和本地测试稳定通过。
- 原始 Agent 行为被测试锁定。
- 任意压缩与恢复路径均不会拆散 Tool Call/Result 事务组。
- 一条命令可运行基线评测并生成机器可读报告。
- Python 支持版本和质量工具链已经与项目配置一致。

### M1：确定性的 Tool Runtime

任务：

- 实现 `ToolSpec`、`ToolResult` 和实例级 Tool Registry。
- 修复 `self.tools` 与全局 `get_tool()` 不一致问题。
- 使用 Pydantic 或等价机制校验参数。
- 实现副作用感知 Scheduler：只读工具可并发，写入、Shell 和 Git 默认串行。
- 实现 PathGuard、命令风险分级、超时和输出上限。
- 实现 `PolicyDecision`、`ApprovalRequest` 和可测试的 Policy Engine。
- 固化“校验 -> 策略 -> 审批 -> 调度 -> 执行”顺序，并记录每次策略决策。
- 清除 Bash cwd、变更文件集合等不必要的进程级共享状态。

验收：

- Agent 只能调用当前实例显式注册的工具。
- 副作用工具不存在并发竞态。
- 未获得 `allow` 的 Tool Handler 从未被执行，`ask` 决策可以通过 CLI 明确批准或拒绝。
- 固定 Safety Suite 零违规。
- M0 基线任务无未解释回归。

### M2：Agent Runtime 与最小可观测性

任务：

- 实现 `TaskSpec`、`TaskRun`、`PlanStep` 和 Artifact。
- 实现显式状态机、Budget、终止策略和结构化错误分类。
- 实现 PlanStep 状态约束、完成证据和计划修订记录。
- 抽离 Provider 接口，但不提前拆分大量空包。
- 实现 Planner、Executor、Verifier 的最小接口。
- 实现分段式 PromptAssembler 和最小生命周期中间件。
- 实现模型瞬时错误退避、Context Overflow 单次紧急压缩和副作用重试约束。
- 同步实现 Event Bus 和 JSONL Event Sink。
- CLI 增加按 Run ID 查看状态、当前步骤、完成比例和事件的最小能力。

验收：

- 每次状态迁移、模型调用和工具调用均可追踪。
- 同一个 Run 最多一个 `in_progress` 步骤，已完成步骤均有机器可读证据。
- 重复失败、超时和预算耗尽会可靠终止。
- Runtime 可使用 Fake Provider 完成离线集成测试。
- 可通过 JSONL 重建单次运行的关键时间线。

### M3：Workspace、Git 与验证闭环

任务：

- 实现 WorkspaceManager 和 Git Worktree。
- 实现 Worktree 生命周期状态、Base Commit 绑定、保留与幂等清理。
- 实现 Git Status、Diff、Apply 和受控 Commit 工具。
- 实现 Test Runner、测试命令发现和结果解析。
- 实现 Verifier、Patch Artifact 和验证报告。
- 增加工作区越界、基础分支污染、脏 Worktree 删除、分支冲突、异常清理和测试超时用例。

验收：

- 每个任务在独立工作区运行。
- 基础分支不被污染。
- Worktree 有未交付修改时默认拒绝删除，异常退出后可以安全恢复或继续清理。
- Patch 可复现，验证结论包含测试证据。
- 失败任务能给出结构化诊断，而不是只有模型文本。

### M4：本地 Issue-to-Patch MVP

任务：

- 实现本地 Issue/Task YAML 导入。
- 构建轻量 Repository Map。
- 按需发现并加载 `AGENTS.md`、`CLAUDE.md`、README、贡献指南、项目配置和测试命令，定义目录级规则优先级与上下文预算。
- 打通 Planner、Executor、Verifier 和有限 Repair Loop。
- 支持任务报告、Patch 导出和失败回放。
- 将评测集扩展到至少 10 个分层任务。

验收：

- CLI 可完整演示从任务描述到 Patch 和验证报告。
- 任务报告记录实际加载的项目规则及其来源，仓库内容不能覆盖系统策略。
- 10 个固定任务可以批量运行并生成指标。
- 公开成功案例、失败案例、成本和限制。

### M5：Checkpoint 与恢复

任务：

- 使用 SQLite 持久化 Task、Run、PlanStep、事件和 Artifact 索引。
- 在状态迁移、文件修改、测试和审批前保存 Checkpoint。
- 实现 `run`、`resume`、`inspect`。
- 增加进程中断、状态不一致和重复恢复的故障注入测试。

验收：

- 进程中断后可从最近一致状态恢复。
- 恢复操作不会重复执行已完成的副作用。
- 故障注入恢复通过率达到 MVP 目标。

### M6：GitHub Issue-to-Draft-PR

任务：

- 实现 GitHub Issue Adapter。
- 生成任务分支、Commit 和结构化 PR 描述。
- 实现人工审批门和最小权限 Token。
- 增加 Secret Scan 和 GitHub Mock API 测试。

验收：

- 可从真实 Issue 创建 Draft PR。
- 未审批不能 Push 或创建 PR。
- PR 包含修改摘要、测试证据、风险和未完成项。

### M7：规模化评测与作品集打磨

任务：

- 将评测集扩展到 20-50 个 L1/L2/L3、Safety 和 Recovery 任务。
- 实现批量 Runner、Grader、失败分类和 Markdown/HTML 报告。
- 开展 Planner、Repository Map、Context Compression 和 Recovery 消融。
- 优化成本、时延和工具调用次数。
- 完善中英文 README、架构图、演示、技术文章、简历和版本发布。

验收：

- 一条命令可复现全部公开指标。
- README 展示基线、最终结果、消融和失败案例。
- 至少一项优化有可复现的数据收益。
- 新用户可在 10 分钟内跑通 Demo。

### 主线外 Backlog（M7 后按评测决定）

以下能力只有在单 Agent Issue-to-Patch 主线出现可量化瓶颈后再立项：

- 自动长期 Memory 的筛选、提取和整理。
- 后台任务与 Cron 调度。
- Multi-Agent、异步邮箱、团队协议和自主任务认领。
- MCP 与外部插件市场。
- 面向第三方扩展的通用 Hook SDK。

这些能力必须作为独立实验进行基线、收益和复杂度评估，不得仅因为参考项目包含对应章节就进入主线。

## 19. 优先级与时间安排

```text
M0 基线与评测
    -> M1 Tool Runtime
    -> M2 Runtime + JSONL Events
    -> M3 Workspace + Git + Verifier
    -> M4 Issue-to-Patch MVP
    -> M5 Checkpoint
    -> M6 Issue-to-Draft-PR
    -> M7 规模化评测与作品集
```

按你每天投入 9 小时、每周有效开发 6 天计算，名义投入约 54 小时。考虑学习、调试、返工和文档时间，建议按 5-7 周安排，而不是简单按总工时线性压缩：

| 时间 | 里程碑 | 主要交付 |
|---|---|---|
| 第 1 周 | M0-M1 前半 | 基线、协议不变量、Fake Provider、Registry、ToolResult |
| 第 2 周 | M1-M2 | Scheduler、Policy Engine、状态机、PlanStep、JSONL Events |
| 第 3 周 | M3 | Worktree 生命周期、Git、Test Runner、Verifier |
| 第 4 周 | M4 | 项目规则加载、Issue-to-Patch MVP、10 任务评测 |
| 第 5 周 | M5-M6 | SQLite Checkpoint、故障注入、GitHub Draft PR 和审批 |
| 第 6-7 周 | M7 | 20-50 任务、消融、优化、文档、演示和缓冲 |

第 4 周结束时必须形成可投递的第一个版本。第 5-7 周用于增强恢复、GitHub 集成和作品集质量，不能让后续功能阻塞 M0-M4 的完整交付。

## 20. 风险控制

| 风险 | 控制措施 |
|---|---|
| 范围持续膨胀 | 坚持 Issue-to-Patch 单一主线 |
| 模型输出不稳定 | Fake Provider、结构化协议、重试上限 |
| Agent 破坏仓库 | Worktree、Path Guard、Policy Engine、审批策略 |
| Token 成本过高 | 分层上下文、缓存、模型路由 |
| 压缩破坏消息协议 | Tool Call/Result 事务组不变量与回归测试 |
| 只有 Demo 没有指标 | 建立任务集、基线、消融和失败报告 |
| 过早引入多 Agent | 单 Agent 达到可测瓶颈后再实验 |
| GitHub Token 泄露 | Adapter 隔离、脱敏和最小权限 |
| 测试命令失控 | 超时、输出限制、资源和进程清理 |

## 21. ADR 与文档交付

首批 ADR：

1. 单 Agent 状态机而非多 Agent。
2. Tool Registry 实例化和显式注入。
3. 副作用工具默认串行。
4. SQLite 作为首版持久化方案。
5. Git Worktree 隔离任务。
6. Repository Map 首版不使用向量数据库。
7. PR 创建必须人工审批。
8. Coding Agent 评测如何保证可复现。
9. Policy Engine、生命周期中间件和 Event Bus 的职责边界。
10. Tool Call/Result 事务组为何不能在压缩时拆分。

文档结构：

```text
README.md
docs/
├── architecture.md
├── workflow.md
├── security.md
├── evaluation.md
├── development.md
├── demo.md
├── adr/
└── reports/
    ├── baseline.md
    └── final-evaluation.md
examples/
├── local-task.yaml
└── github-issue.yaml
```

README 首屏必须回答：解决什么问题、与普通 LLM Demo 的区别、核心架构、一条命令如何运行、当前指标和演示效果。

## 22. 简历与面试交付

项目名称建议：

**CodingAgent：可恢复、可评测的 Issue-to-PR Coding Agent**

简历描述模板，发布前使用真实数据替换占位符：

- 基于 Python 构建 Coding Agent Runtime，以显式状态机编排规划、工具执行、测试验证和失败恢复，实现从 GitHub Issue 到 Draft PR 的端到端闭环。
- 设计类型安全的 Tool Registry 与副作用感知调度器，通过路径隔离、命令分级和审批控制文件、Shell 与 GitHub 操作风险。
- 基于 SQLite Checkpoint 和结构化事件实现中断恢复与全链路追踪，记录 Token、耗时、工具调用和测试证据。
- 构建包含 `N` 个缺陷任务的自动评测集，使测试通过任务率从 `A%` 提升至 `B%`，平均成本降低 `C%`。

面试重点：

1. Agent Loop 为什么会失控，如何保证终止？
2. 为什么工具调用不能全部并行？
3. 如何阻止模型执行危险命令？
4. 如何判断任务真的完成？
5. 上下文压缩后如何保留关键状态？
6. 为什么权限判断必须发生在 Tool Handler 执行之前？
7. Checkpoint 如何处理数据库与代码状态不一致？
8. Coding Agent 成功率如何客观评测？
9. 为什么当前阶段不使用多 Agent？
10. Repository Map 与向量检索如何取舍？
11. 如何权衡模型质量、时延和成本？

## 23. Definition of Done

单项功能完成要求：

- 需求、边界、类型和错误处理明确。
- 有自动化测试和结构化日志。
- Tool Call/Result、状态迁移和权限决策满足协议不变量。
- 文档与配置同步更新。
- 不引入未授权权限。
- 评测集上无明显回归。
- 输入、过程和输出证据可验证。

项目完成要求：

- Issue 到 Draft PR 的闭环可稳定演示。
- 安全、恢复、评测和可观测性均有真实实现。
- 至少 20 个任务可重复运行并生成报告。
- CI、文档、演示和简历材料完整。
- 所有公开指标均可由仓库脚本复现。

## 24. 立即执行清单

按 M0 顺序执行：

1. 明确 Python 版本支持策略，并同步 `pyproject.toml`、CI 和文档。
2. 将 Ruff、Coverage 和选定的类型检查器加入开发依赖。
3. 绘制现有模块依赖图、Agent Loop 时序图和消息数据流图。
4. 为 Tool Call 循环、自定义工具注册、并行副作用和上下文压缩增加回归测试，优先锁定 Tool Call/Result 事务组不变量。
5. 实现确定性的 Fake Provider。
6. 建立首批 5-10 个固定评测任务和机器可读任务格式。
7. 运行原始 Agent 基线，记录成功率、Patch、耗时、Token 和失败类型。
8. 新增 ADR-001，确认“单 Agent 状态机 + Issue-to-Patch 主线”。
9. 将 `AgentTool` 从默认工具集移除或置于 Feature Flag 后。
10. 设计 `ToolSpec`、`ToolResult`、`PolicyDecision`、`ApprovalRequest` 和实例级 `ToolRegistry` 接口，作为 M1 输入。

M0 完成门槛是“测试稳定、基线可复现、决策有记录”。第一项功能里程碑仍是 M1 的“安全、确定性的 Tool Runtime”，不是 GitHub UI、多 Agent 或 RAG。
