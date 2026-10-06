# Security Agent v0.1

最小可运行的 Agent Runtime，用于验证任务派发与状态回写的数据流。
仅使用 Python 标准库，需要 Python 3.10 或更新版本，无需安装依赖。

## 运行

在项目目录执行：

```powershell
python main.py
```

示例注册两个 Mock Agent，创建并记录任务 T1，再由 Supervisor 派发代码分析任务。
输出 Agent 日志、返回结果、`COMPLETED` 任务状态和 observations。
`./demo_app` 只是演示目标字符串，无需创建该目录。

## 结构

```text
security_agent/
    agents/
        code_analysis.py
        verification.py
    models/
        task.py
    runtime/
        registry.py
        supervisor.py
    tests/
        test_runtime.py
    main.py
    state.py
```

- `Task`：dataclass 任务模型，默认状态为 `PENDING`。
- `AgentState`：保存目标、阶段、任务、发现、证据和观察结果。
- `AgentRegistry`：保存 Agent 实例与声明的 capabilities，不承担安全策略判断。
- `Supervisor`：查找 Agent、检查 capability、执行任务、记录 observation。
- `CodeAnalysisAgent` / `VerificationAgent`：固定返回成功结果的 Mock。

## 执行约定

```text
Task -> Supervisor -> Registry -> Agent
             |                     |
             +---- AgentState <----+ Observation
```

调用方先用 `state.add_task(task)` 记录任务，再执行
`supervisor.delegate(task, state)`。任务以同一对象保存在 state 中，
因此 Supervisor 修改任务状态后，`state.tasks` 中也能看到更新。

| 情况 | delegate 返回值 | 任务状态 | observations |
| --- | --- | --- | --- |
| Agent 正常返回 | Agent 原始结果 | `PENDING -> RUNNING -> COMPLETED` | 追加结果 |
| Agent 未注册 | `status=DENIED, reason=UNKNOWN_AGENT` | 保持不变 | 不追加 |
| action 不在 capabilities 中 | `status=DENIED, reason=CAPABILITY_NOT_ALLOWED` | 保持不变 | 不追加 |
| Agent 抛出异常 | `status=FAILED, reason=异常消息` | `PENDING -> RUNNING -> FAILED` | 不追加 |

沿用提供的设计，拒绝派发不会把任务标记为失败。v0.1 不校验结果 schema，
正常返回即表示执行完成；尚不解析 Agent 自报的失败状态，也不限制重复派发。
调用方应为每次执行创建独立任务并提供唯一 ID，当前没有调度器或去重机制。

`main.py` 默认只执行分析任务。VerificationAgent 已注册 `verify_sqli`，
测试中会完整执行分析和验证两个任务，但不会根据分析结果自动派生验证任务。

## 边界

两个 Agent 均为 Mock，不读取代码、不发送网络请求、不执行实际漏洞验证。
输出的 `SQL Injection` 是固定演示数据，不代表目标存在漏洞；
`COMPLETED` 只代表任务执行结束，不代表漏洞被确认。
`potential_findings` 仅保存在 observation 内，不写入 `state.findings`。

本版不引入 Pydantic、Schema Validation、Policy、Scope、HITL、PendingAction、
Task Graph、Scheduler、FindingEvaluator、StateManager、LLM 或 MCP。
`findings` 和 `evidence` 保留为空列表，尚无发现评估或证据系统。

## 测试

```powershell
python -m unittest discover -s tests -v
```

覆盖 Task 默认状态、State 数据隔离与写入、Registry 查询、成功派发、
未知 Agent、越权 capability、执行异常、双 Agent 数据流和命令行示例。
