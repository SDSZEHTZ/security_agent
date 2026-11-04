# Security Agent Runtime v0.6

保留 Registry、Scheduler、Supervisor、Evidence、HITL 的原有分层，
新增 LLM Planner、结构化任务分解和按阶段重新规划。

```text
User Goal → Planner → PlanProposal → PlanValidator → PlanCompiler
                    → Runtime-owned Tasks → Scheduler → Supervisor → Agent
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
.venv/Scripts/python.exe main.py
```

默认使用离线 DemoPlanner，无需 API Key，不调用模型。
演示依次产生潜在 SQL Injection Finding、MEDIUM 证据和 UNCONFIRMED 状态，
最后执行 Mock 报告任务并打印 Runtime 的任务、观察、证据和发现。

启用真实 LLM Planner：

```powershell
$env:OPENAI_API_KEY = "<your-api-key>"
.venv/Scripts/python.exe main.py --model "<支持 Structured Outputs 的模型>" --target "./demo_app" --goal "检查授权目标的 Web 安全问题"
```

模型名由调用者指定，不在源码中硬编码。LLM 使用 Responses API 的
`responses.parse(text_format=PlanProposal)`；处理拒绝、空解析结果、未完成响应和请求异常。
请求设置 `store=False`、60 秒超时、最多 2 次 SDK 重试及输出 token 上限。
初始化客户端本身不发送模型请求。结构化输出仍须通过 Runtime 语义校验。
接口参考：[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)。

**所有 Agent 仍是 Mock**：不读取真实代码、不发送漏洞验证请求、不执行系统命令。
真实 LLM 模式只改变规划方式，不会把 Mock Agent 变成真实扫描器。
ReportAgent 是演示任务；控制台展示的 Finding/Evidence 来自 Runtime，并非 LLM 安全结论。

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

单元测试使用 Mock/DemoPlanner，不联网。覆盖原有安全控制、动态上下文、
编译、非法计划、空阶段、超时传播、审批暂停恢复、防重放及 Finding 关联。

真实 API 测试与单元测试分目录，默认跳过；手动开启会产生 API 费用：

```powershell
$env:RUN_LLM_INTEGRATION = "1"
$env:OPENAI_MODEL = "<支持 Structured Outputs 的模型>"
# OPENAI_API_KEY 需已设置
.venv/Scripts/python.exe -m unittest discover -s integration_tests -v
```

审计问题、修复和适用范围见 [AUDIT_v0.6.md](AUDIT_v0.6.md)。
