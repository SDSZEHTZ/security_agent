# Security Agent Runtime v0.7

保留 Registry、Scheduler、Supervisor、Evidence、HITL 的原有分层，
在按阶段规划的基础上，接入真实源码工具与受控 HTTP 基线检查。

```text
User Goal → Planner → PlanProposal → PlanValidator → PlanCompiler
                    → Runtime-owned Tasks → Scheduler → Supervisor → ToolContext
                    → Agent → ToolExecutor → ToolRegistry → Tool
                    → Observation → Evidence / Finding → 下一阶段重新规划
```

Runtime 按 ANALYZE → VERIFY → REPORT → END 推进；Planner 只能建议当前阶段的任务，
不能修改阶段、权限、Task ID 或 State。每个阶段最多 10 个任务，最多规划三个阶段。
本版不做 Observation-level Re-plan、并发执行或持久化恢复。

## 安装和运行

需要 Python 3.10+。在仓库根目录运行：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe main.py --target .
```

默认使用离线 DemoPlanner，无需 API Key，不调用模型。
演示在授权目录搜索 `execute(`，记录真实命中，再执行 Mock 报告任务。
关键词命中不自动生成 Finding 或 Evidence，因此默认演示不会规划 SQLi/SSRF 验证。
`--target` 必须指向存在的源码目录；默认值 `./demo_app` 保留，但仓库未附带该目录。

授权 HTTP Origin（与源码目录分开）：

```powershell
.venv/Scripts/python.exe main.py --target . --origin http://127.0.0.1:5000
```

`--origin` 只设置授权范围，DemoPlanner 暂不自动创建 HTTP 任务。
成功的 baseline 结果保存在 `Observation.data["http_baseline"]`，只包含响应元信息；不会生成 Finding/Evidence。
`check_http_baseline` 在 VERIFY 阶段由 VerificationAgent 执行，默认 `HEAD /`，
允许 `GET` / `HEAD` 和 Origin 相对路径；禁止更换 Host、跟随重定向或使用代理，
采用 3 秒请求超时和 64 KiB 响应读取上限。它只记录 Observation，不确认漏洞。

启用真实 LLM Planner：

```powershell
$env:OPENAI_API_KEY = "<your-api-key>"
.venv/Scripts/python.exe main.py --model "<支持 Structured Outputs 的模型>" --target . --goal "搜索源码中的 execute( 调用，analyze_code 参数使用 query=execute("
```

模型名由调用者指定，不在源码中硬编码。LLM 使用 Responses API 的
`responses.parse(text_format=PlanProposal)`；处理拒绝、空解析结果、未完成响应和请求异常。
请求设置 `store=False`、60 秒超时、最多 2 次 SDK 重试及输出 token 上限。
初始化客户端本身不发送模型请求。结构化输出仍须通过 Runtime 语义校验。
接口参考：[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)。

CodeAnalysisAgent 已实际调用 `search_code` / `read_source`，HTTP baseline 也使用真实工具。
`verify_sqli`、`verify_ssrf` 仍是教学模拟，不代表真实漏洞验证；不执行系统命令。
ReportAgent 是演示任务；控制台展示的 Finding/Evidence 来自 Runtime，并非 LLM 安全结论。

任务参数：`analyze_code` 需要字符串 `query`，可选 `max_matches`（Agent 默认 20）；
`read_file` 需要授权目录内的相对 `path`；`check_http_baseline` 接受 `path`、`method`。
本版未增加 Planner 工具感知或源码回传能力；使用 LLM Planner 时应在目标说明中明确参数。

## 安全边界

- PlanValidator 检查 schema、phase、任务上限、Agent、capability、目标、Finding、依赖与环。
- PlanCompiler 分配不冲突的 Task ID，将局部 key 映射为 Runtime 依赖 ID。
- Scheduler 仅派发当前阶段任务，拒绝指向未来阶段的依赖；失败、阻断和超时会阻断下游任务。
- Supervisor 在执行和批准时重新检查 Workflow、Capability、Policy、Scope、Phase、依赖及 Finding 关联。
- Scope 保持原有的**目标字符串精确相等**规则；不自动授权子路径、子域名或其他等价写法。
- LLM 规划的验证任务必须引用已有、类型和目标匹配、未终结的 Finding。
  旧手动派发接口允许无 Finding 的验证任务，但不会生成关联证据。
- 分析结果中仅接收已知类型 SQL Injection / SSRF；Runtime 分配 Finding ID、
  使用已授权目标、设置 POTENTIAL，并按目标和类型去重。
- 审批快照包含 phase、finding_id 和不可变依赖列表；审批绑定原 State，
  同一任务重复派发和审批重放被拒绝。
- Agent 接收冻结请求，不接收 Runtime 的可变 Task 或全局 State。
- Supervisor 在检查通过后创建冻结 ToolContext；授权目录和 Origin 取自 State，
  不取自任务参数。此边界约束 Planner 输入，不是对任意 Python Agent 的进程隔离。
- Agent capability 与工具权限分别校验：分析可搜索/读取，read_file 只可读取，
  baseline 只可调用 HTTP 工具；其余 Agent/action 默认没有工具权限。
- 工具参数错误、权限拒绝及执行 ERROR 映射为 FAILED Observation 和 FAILED Task；
  本版工具超时也映射为 FAILED，不扩展 ToolResult 的状态枚举。
- PlanningContext 只保留最近 5 条观察的白名单信号、最多 50 个 Finding、
  最近 30 个已完成任务 ID；原始响应、源码、任意字段及嵌套数据不传入 Planner。
- 先校验完整候选任务图，再写入任务并标记阶段已规划。
  规划失败返回 BLOCKED，保持该阶段未规划，可以在修正原因后重试。
- 空计划可以推进；WAITING_CONFIRMATION 不推进；恢复执行不会重复规划已规划阶段。

`COMPLETED` 表示 Workflow 结束，不代表全部任务成功或漏洞已确认；
返回值的 `failed_task_ids` 列出失败、阻断、超时的任务。
只有运行完成且该列表为空时 CLI 返回退出码 0。

## HITL 暂停与恢复

`verify_ssrf` 默认需要人工批准，`execute_command` 默认拒绝。
Runtime 返回 WAITING_CONFIRMATION、task_ids、action_ids 后由调用方展示审批请求。
以下操作应仅在用户明确批准对应 action_id 后执行：

```python
result = runtime.run_until_blocked(goal, state)
# 调用方在收到真实用户批准后：
approval_result = runtime.supervisor.approve(approved_action_id, state)
result = runtime.run_until_blocked(goal, state)
```

保留同一个 runtime 和 state 实例。CLI 是单次运行示例，不提供交互审批界面；
进程退出后内存中的审批不会持久化。示例不会自动批准任何任务。

## 测试

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

测试使用 Mock/DemoPlanner，并通过 `127.0.0.1` 临时 HTTP 服务验证真实请求；不访问公网。
覆盖原有安全控制、动态上下文、
编译、非法计划、空阶段、超时传播、审批暂停恢复、防重放及 Finding 关联。

真实 API 测试与单元测试分目录，默认跳过；手动开启会产生 API 费用：

```powershell
$env:RUN_LLM_INTEGRATION = "1"
$env:OPENAI_MODEL = "<支持 Structured Outputs 的模型>"
# OPENAI_API_KEY 需已设置
.venv/Scripts/python.exe -m unittest discover -s integration_tests -v
```

审计问题、修复和适用范围见 [AUDIT_v0.6.md](AUDIT_v0.6.md)。
