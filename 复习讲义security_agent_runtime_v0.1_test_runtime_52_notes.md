# Security Agent Runtime v0.1 测试代码详解复习笔记

> 本文整理自对 `test_runtime.py` 的 52 条逐步解析，重点不是死记 `unittest` 语法，而是理解测试数据如何从创建、传入、Runtime 内部流转、返回，再到断言验证。

---

## 总体结构

这份 `test_runtime.py` 主要测试四层：

```text
StateTests
→ Task / AgentState

RegistryTests
→ AgentRegistry

SupervisorTests
→ Runtime 核心执行路径

MainTests
→ 整个程序入口 main()
```

整个 Runtime 的核心数据流：

```text
测试代码创建 Task / State / Agent
            ↓
       Supervisor.delegate()
            ↓
        Registry.get()
            ↓
       Capability Check
            ↓
      task.status = RUNNING
            ↓
         Agent.run()
            ↓
        返回 Observation
            ↓
 state.add_observation()
            ↓
   task.status = COMPLETED
            ↓
          return
            ↓
 unittest 检查最终结果
```

---

# 1. `unittest`

```python
import unittest
```

Python 自带的测试框架。

后面写：

```python
class StateTests(unittest.TestCase):
```

就是告诉 Python：

> 这是一个测试类。

类中所有：

```python
def test_xxx(self):
```

都会被自动识别为测试。

---

# 2. `io` 和 `redirect_stdout`

```python
import io
from contextlib import redirect_stdout
```

主要用于测试 `main()` 的打印内容。

正常：

```python
print("hello")
```

会打印到终端。

但测试时我们想检查 `main()` 到底打印了什么，于是：

```python
output = io.StringIO()
```

创建一个内存中的字符串缓冲区。

然后：

```python
with redirect_stdout(output):
    main()
```

这段代码中的所有 `print()` 都会写入 `output`，而不是实际终端。

最后：

```python
text = output.getvalue()
```

拿到所有输出文本。

---

# 3. `Mock`

```python
from unittest.mock import Mock
```

Mock 可以理解成：

> 一个假的 Agent。

当我们只想测试 `Supervisor` 是否正确调用 Agent 时，不需要真实运行 `CodeAnalysisAgent`。

因此：

```python
agent = Mock()
```

创建一个假对象。

可以指定：

```python
agent.run.side_effect = run
```

让调用 `agent.run()` 时执行自定义函数。

也可以：

```python
agent.run.side_effect = RuntimeError("Mock execution failed")
```

模拟 Agent 执行失败。

核心目的：

> 单独测试 Supervisor，不让真实 Agent 的实现干扰测试。

---

# 4. `StateTests`

```python
class StateTests(unittest.TestCase):
```

这个测试类主要负责：

```text
Task
AgentState
```

不测试 Supervisor。

---

# 5. `test_task_defaults_to_pending`

```python
def test_task_defaults_to_pending(self):
    task = Task("T1", "CodeAnalysisAgent", "analyze_code", "./demo_app")
    self.assertEqual(task.status, "PENDING")
```

假设 `Task`：

```python
@dataclass
class Task:
    id: str
    agent: str
    action: str
    target: str
    status: str = "PENDING"
```

那么：

```python
Task("T1", "CodeAnalysisAgent", "analyze_code", "./demo_app")
```

对应：

```text
id     = "T1"
agent  = "CodeAnalysisAgent"
action = "analyze_code"
target = "./demo_app"
```

没有传 `status`，因此自动使用默认值：

```text
PENDING
```

最后：

```python
self.assertEqual(task.status, "PENDING")
```

检查默认状态是否正确。

---

# 6. `test_state_defaults_and_mutations`

```python
def test_state_defaults_and_mutations(self):
```

测试两件事：

```text
1. State 初始状态是否正确
2. add_task / add_observation 是否能正确修改 State
```

创建：

```python
state = AgentState("./demo_app")
```

此时：

```text
state
├── target = "./demo_app"
├── phase = "ANALYZE"
├── tasks = []
├── observations = []
├── findings = []
└── evidence = []
```

---

# 7. 创建 Task 和 Observation

```python
task = Task("T1", "CodeAnalysisAgent", "analyze_code", state.target)
```

其中：

```python
state.target
```

就是：

```text
"./demo_app"
```

因此等价于：

```python
Task("T1", "CodeAnalysisAgent", "analyze_code", "./demo_app")
```

然后：

```python
observation = {"task_id": task.id}
```

得到：

```python
{
    "task_id": "T1"
}
```

这里没有真的运行 Agent。

只是手工造一条 Observation，用来测试：

```python
state.add_observation()
```

---

# 8. 检查 AgentState 初始化

```python
self.assertEqual(state.target, "./demo_app")
self.assertEqual(state.phase, "ANALYZE")
self.assertEqual(state.tasks, [])
self.assertEqual(state.observations, [])
self.assertEqual(state.findings, [])
self.assertEqual(state.evidence, [])
```

这组断言是在锁定 AgentState 的默认设计。

如果以后不小心把：

```python
self.phase = "VERIFY"
```

或者：

```python
self.tasks = None
```

测试就会失败。

---

# 9. 修改 State

```python
state.add_task(task)
state.add_observation(observation)
```

如果实现是：

```python
def add_task(self, task):
    self.tasks.append(task)

def add_observation(self, observation):
    self.observations.append(observation)
```

执行后：

```text
state.tasks
=
[task]
```

以及：

```text
state.observations
=
[observation]
```

---

# 10. `assertIs` 和 `assertEqual`

```python
self.assertIs(state.tasks[0], task)
```

`assertEqual(a, b)`：

> 检查内容是否相等。

`assertIs(a, b)`：

> 检查是不是内存中的同一个对象。

例如：

```python
a = {"x": 1}
b = {"x": 1}
```

则：

```python
a == b
```

为：

```text
True
```

但：

```python
a is b
```

为：

```text
False
```

因为它们内容一样，但不是同一个对象。

所以：

```python
self.assertIs(state.tasks[0], task)
```

验证的是：

> `add_task()` 放入 State 的是原来的 task 对象本身，而不是重新复制一份。

---

# 11. `test_state_collections_are_not_shared`

```python
def test_state_collections_are_not_shared(self):
```

这个测试防止一个经典 Python bug：

> 不同 AgentState 错误地共享同一个 list。

创建：

```python
first = AgentState("./first")
second = AgentState("./second")
```

我们希望：

```text
first.tasks
```

和：

```text
second.tasks
```

是两个不同列表。

否则：

```python
first.tasks.append(task)
```

可能会导致：

```python
second.tasks
```

也发生变化。

---

# 12. `for` + tuple

```python
for name in ("tasks", "findings", "evidence", "observations"):
```

这里：

```python
("tasks", "findings", "evidence", "observations")
```

是 tuple（元组）。

循环依次：

```text
name = "tasks"
name = "findings"
name = "evidence"
name = "observations"
```

避免重复写四遍测试代码。

---

# 13. `subTest`

```python
with self.subTest(collection=name):
```

作用：

> 把循环中的每一次检查标记成一个独立的小测试。

如果 `evidence` 出错，测试报告可以显示：

```text
collection='evidence'
```

更方便定位问题。

---

# 14. `getattr`

```python
getattr(first, name)
```

如果：

```python
name = "tasks"
```

那么：

```python
getattr(first, "tasks")
```

等价于：

```python
first.tasks
```

所以 `getattr()` 的作用是：

> 用字符串动态访问对象属性。

最后：

```python
self.assertIsNot(getattr(first, name), getattr(second, name))
```

检查：

```text
first.tasks is not second.tasks
first.findings is not second.findings
first.evidence is not second.evidence
first.observations is not second.observations
```

---

# 15. `RegistryTests`

这一组开始测试：

```text
AgentRegistry
```

---

# 16. `test_registration_and_lookup`

```python
registry = AgentRegistry()
agent = CodeAnalysisAgent()

registry.register(
    "CodeAnalysisAgent",
    agent,
    ["analyze_code"]
)
```

注册后，Registry 大致：

```python
{
    "CodeAnalysisAgent": {
        "instance": agent,
        "capabilities": ["analyze_code"]
    }
}
```

然后：

```python
info = registry.get("CodeAnalysisAgent")
```

得到：

```python
{
    "instance": agent,
    "capabilities": ["analyze_code"]
}
```

测试：

```python
self.assertIs(info["instance"], agent)
```

确保 Registry 保存的是原 Agent 对象。

再测试：

```python
self.assertEqual(info["capabilities"], ["analyze_code"])
```

确保 capability 正确。

---

# 17. Unknown Agent

```python
self.assertIsNone(AgentRegistry().get("UnknownAgent"))
```

可以拆成：

```python
registry = AgentRegistry()
result = registry.get("UnknownAgent")
self.assertIsNone(result)
```

因为：

```python
dict.get("不存在的key")
```

默认返回：

```python
None
```

这就是 Supervisor 后面可以写：

```python
if agent_info is None:
```

的原因。

---

# 18. Registry 为什么要复制 capabilities

```python
capabilities = ["analyze_code"]

registry.register(
    "CodeAnalysisAgent",
    CodeAnalysisAgent(),
    capabilities
)

capabilities.append("verify_sqli")
```

如果 Registry 直接保存：

```python
"capabilities": capabilities
```

那么保存的是同一个 list 的引用。

之后外部：

```python
capabilities.append("verify_sqli")
```

Registry 内部的 capability 也会被一起修改。

测试：

```python
self.assertEqual(
    registry.get("CodeAnalysisAgent")["capabilities"],
    ["analyze_code"]
)
```

要求：

> Registry 应保存一个独立副本。

因此注册时适合：

```python
capabilities.copy()
```

或者：

```python
list(capabilities)
```

这里是一层简单 list，所以浅拷贝通常就足够。

---

# 19. `SupervisorTests`

这部分真正测试完整链：

```text
Task
↓
Supervisor
↓
Registry
↓
Agent
↓
Observation
↓
State
```

---

# 20. `setUp()`

```python
def setUp(self):
```

`unittest` 会在每一个测试执行前自动调用一次。

例如有：

```text
test_success
test_unknown
test_unsupported
test_exception
test_both_agents
```

实际执行顺序类似：

```text
setUp
→ test_success

重新 setUp
→ test_unknown

重新 setUp
→ test_unsupported

重新 setUp
→ test_exception

重新 setUp
→ test_both_agents
```

因此每个 test 都得到一套干净状态。

---

# 21. `setUp()` 创建的数据

```python
self.state = AgentState("./demo_app")
self.registry = AgentRegistry()
self.supervisor = Supervisor(self.registry)
```

此时 Registry 还是空的。

然后：

```python
self.task = Task(
    "T1",
    "CodeAnalysisAgent",
    "analyze_code",
    self.state.target
)
```

得到：

```text
T1
agent = CodeAnalysisAgent
action = analyze_code
target = ./demo_app
status = PENDING
```

最后：

```python
self.state.add_task(self.task)
```

State：

```text
tasks = [T1]
observations = []
```

---

# 22. 成功执行测试整体目标

```python
def test_success_records_observation_and_completes_task(self):
```

这个 test 要验证完整 happy path：

```text
Task
↓
找到 Agent
↓
Capability PASS
↓
RUNNING
↓
Agent.run()
↓
返回 Observation
↓
记录 Observation
↓
COMPLETED
```

---

# 23. 手工创建预期 Observation

```python
observation = {
    "agent": "CodeAnalysisAgent",
    "task_id": "T1",
    "execution_status": "SUCCESS",
    "data": {},
}
```

这不是 Runtime 自动生成的。

而是测试提前准备：

> 假 Agent 等会儿应该返回这份结果。

---

# 24. 在 test 内部定义 `run()`

```python
def run(task):
    self.assertIs(task, self.task)
    self.assertEqual(task.status, "RUNNING")
    self.assertEqual(self.state.observations, [])
    return observation
```

这是函数里面再定义函数。

它只在当前 test 中使用。

第一条：

```python
self.assertIs(task, self.task)
```

检查 Supervisor 传给 Agent 的是不是原 Task 对象。

第二条：

```python
self.assertEqual(task.status, "RUNNING")
```

验证 Supervisor 是否在调用 Agent 之前就先把 Task 改为 RUNNING。

因此顺序必须是：

```text
task.status = RUNNING
↓
agent.run(task)
```

不能反过来。

---

# 25. Agent 执行时 Observation 必须还是空

```python
self.assertEqual(self.state.observations, [])
```

为什么？

因为合理顺序应该是：

```text
Agent 执行
↓
产生 Observation
↓
Runtime 保存 Observation
```

Agent 还没返回时，State 不应该提前出现结果。

因此这个断言实际上是在检查：

> Observation 的写入时机。

---

# 26. `Mock()` + `side_effect`

```python
agent = Mock()
agent.run.side_effect = run
```

这表示：

> 有人调用 `agent.run(...)` 时，不执行真实 Agent，而执行上面定义的 `run(...)`。

因此 Supervisor 中：

```python
agent_info["instance"].run(task)
```

实际会变成：

```python
run(task)
```

---

# 27. 注册 fake Agent

```python
self.registry.register(
    self.task.agent,
    agent,
    [self.task.action]
)
```

其中：

```text
self.task.agent
=
"CodeAnalysisAgent"
```

以及：

```text
self.task.action
=
"analyze_code"
```

所以等价于：

```python
registry.register(
    "CodeAnalysisAgent",
    fake_agent,
    ["analyze_code"]
)
```

---

# 28. `Supervisor.delegate()` 数据开始流动

```python
result = self.supervisor.delegate(
    self.task,
    self.state
)
```

进入 Supervisor 后：

```python
agent_info = registry.get(task.agent)
```

即：

```python
registry.get("CodeAnalysisAgent")
```

找到 Mock Agent。

然后 Capability Check：

```python
if task.action not in agent_info["capabilities"]:
```

当前：

```text
"analyze_code" in ["analyze_code"]
```

所以 PASS。

然后：

```python
task.status = "RUNNING"
```

状态：

```text
PENDING → RUNNING
```

---

# 29. Mock Agent 真正被调用

Supervisor：

```python
result = agent.run(task)
```

因为：

```python
agent.run.side_effect = run
```

所以实际执行：

```python
run(self.task)
```

内部确认：

```text
传入的是原 Task ✔
Task 已经 RUNNING ✔
Observation 仍为空 ✔
```

然后：

```python
return observation
```

返回之前手工构造的 observation。

---

# 30. Supervisor 收到 Observation

此时：

```python
result = observation
```

然后：

```python
state.add_observation(result)
```

State：

```text
observations:
[]
↓
[observation]
```

随后：

```python
task.status = "COMPLETED"
```

状态：

```text
RUNNING → COMPLETED
```

最后：

```python
return result
```

回到测试代码。

---

# 31. `assert_called_once_with`

```python
agent.run.assert_called_once_with(self.task)
```

Mock 专用断言。

它同时检查：

```text
agent.run 调用次数 = 1
调用参数 = self.task
```

---

# 32. 同一个 Observation 对象

```python
self.assertIs(result, observation)
self.assertIs(self.state.observations[0], observation)
```

说明：

```text
observation
result
state.observations[0]
```

三者都指向同一个 dict。

内存图：

```text
                ┌──────────────────────┐
observation ───→│ {                    │
result ────────→│  agent: ...          │
state.obs[0] ──→│  task_id: T1         │
                │  SUCCESS             │
                └──────────────────────┘
```

---

# 33. State 中 Task 状态为什么也变了

```python
self.assertEqual(self.task.status, "COMPLETED")
self.assertEqual(self.state.tasks, [self.task])
self.assertEqual(self.state.tasks[0].status, "COMPLETED")
```

原因：

```text
self.task
```

和：

```text
state.tasks[0]
```

是同一个 Task 对象。

Supervisor 修改：

```python
self.task.status
```

State 中看到的就是同一个对象的新状态。

并不是 Runtime 更新了两遍。

---

# 34. Finding / Evidence 仍为空

```python
self.assertEqual(self.state.findings, [])
self.assertEqual(self.state.evidence, [])
```

因为 v0.1 目前只实现：

```text
Agent Result
↓
Observation
```

还没有：

```text
Observation
↓
Evidence Extraction
↓
Finding Update
```

所以这个测试确保 Supervisor 没有偷偷生成 Finding / Evidence。

---

# 35. Unknown Agent 路径

```python
result = self.supervisor.delegate(self.task, self.state)
```

但 Registry 是空的。

因此：

```python
registry.get("CodeAnalysisAgent")
```

返回：

```python
None
```

于是：

```python
if agent_info is None:
```

成立，立即：

```python
return {
    "status": "DENIED",
    "reason": "UNKNOWN_AGENT"
}
```

后续逻辑不会执行。

所以：

```text
task.status 仍为 PENDING
state.observations 仍为 []
```

---

# 36. Unsupported Capability 路径

注册：

```python
agent = Mock()

self.registry.register(
    self.task.agent,
    agent,
    ["verify_sqli"]
)
```

但 Task 要求：

```text
analyze_code
```

Agent Capability：

```text
verify_sqli
```

因此：

```python
"analyze_code" not in ["verify_sqli"]
```

成立。

Runtime 返回：

```python
{
    "status": "DENIED",
    "reason": "CAPABILITY_NOT_ALLOWED"
}
```

---

# 37. `assert_not_called()` 的安全意义

```python
agent.run.assert_not_called()
```

不是只检查最终 DENIED。

而是检查：

> 被拒绝的任务绝对没有执行 Agent。

这非常重要。

错误写法可能是：

```text
Agent.run()
↓
发现 Capability 不允许
↓
返回 DENIED
```

虽然最终结果是 DENIED，但危险动作已经执行了。

所以安全控制必须：

```text
Validation
↓
Sink
```

而不是反过来。

---

# 38. Agent Exception 路径

```python
agent = Mock()

agent.run.side_effect = RuntimeError(
    "Mock execution failed"
)
```

表示：

> 任何人调用 `agent.run()` 时，直接抛异常。

Supervisor：

```python
try:
    result = agent.run(task)
except Exception as exc:
```

于是进入 `except`。

---

# 39. 异常后状态变化

捕获异常后：

```python
task.status = "FAILED"
```

然后：

```python
return {
    "status": "FAILED",
    "reason": str(exc)
}
```

其中：

```python
str(exc)
```

结果：

```text
Mock execution failed
```

因此返回：

```python
{
    "status": "FAILED",
    "reason": "Mock execution failed"
}
```

---

# 40. 为什么异常时 Observation 为空

因为 Agent 没有正常返回 Observation，而是直接抛异常。

因此：

```python
state.add_observation(result)
```

根本不会执行。

所以：

```python
state.observations == []
```

这也体现：

```text
Tool Failure
≠
Security Negative Result
```

---

# 41. 两个真实 Agent 通过 Runtime

```python
self.registry.register(
    "CodeAnalysisAgent",
    CodeAnalysisAgent(),
    ["analyze_code"]
)

self.registry.register(
    "VerificationAgent",
    VerificationAgent(),
    ["verify_sqli"]
)
```

这里不再用 `Mock()`。

是真实创建两个 Agent 对象。

不过它们当前业务行为仍然是 v0.1 的 demo/mock 逻辑。

---

# 42. 创建第二个 Task

```python
verification = Task(
    "T2",
    "VerificationAgent",
    "verify_sqli",
    self.state.target
)
```

得到：

```text
T2
agent = VerificationAgent
action = verify_sqli
target = ./demo_app
status = PENDING
```

加入 State：

```python
self.state.add_task(verification)
```

于是：

```text
state.tasks
=
[T1, T2]
```

---

# 43. `redirect_stdout(io.StringIO())`

```python
with redirect_stdout(io.StringIO()):
```

两个真实 Agent 中有 `print()`。

测试中并不关心这些打印，所以：

```python
io.StringIO()
```

创建一个临时字符串缓冲区。

`redirect_stdout()` 把输出重定向进去。

因为没有保存这个 StringIO：

> 相当于把打印内容安静地吃掉。

---

# 44. 连续执行两个 Task

先：

```python
analysis_result = self.supervisor.delegate(
    self.task,
    self.state
)
```

流程：

```text
T1
↓
CodeAnalysisAgent
↓
返回 analysis_result
↓
记录 Observation
↓
T1 = COMPLETED
```

再：

```python
verification_result = self.supervisor.delegate(
    verification,
    self.state
)
```

流程：

```text
T2
↓
VerificationAgent
↓
返回 verification_result
↓
记录 Observation
↓
T2 = COMPLETED
```

最后：

```python
state.observations
```

变成：

```python
[
    analysis_result,
    verification_result
]
```

顺序与执行顺序一致。

---

# 45. 检查 Agent 输出 Schema

例如：

```python
self.assertEqual(
    analysis_result["agent"],
    "CodeAnalysisAgent"
)
```

还会检查：

```python
analysis_result["task_id"] == "T1"
analysis_result["execution_status"] == "SUCCESS"
```

这些都在确认 Agent 返回的数据格式符合当前约定。

例如：

```python
analysis_result["data"]["potential_findings"]
```

如果：

```python
analysis_result = {
    "data": {
        "potential_findings": [
            "SQL Injection"
        ]
    }
}
```

则：

```python
analysis_result["data"]
```

先得到：

```python
{
    "potential_findings": ["SQL Injection"]
}
```

再取：

```python
["potential_findings"]
```

得到：

```python
["SQL Injection"]
```

---

# 46. 两个 Task 的最终状态

最后检查：

```python
self.task.status == "COMPLETED"
verification.status == "COMPLETED"
```

Observation：

```python
[
    analysis_result,
    verification_result
]
```

Finding 和 Evidence 继续为空。

因为 v0.1 仍未实现它们。

---

# 47. `MainTests`

这一组不再单独测试某个类。

而是测试：

> 整个 demo 从 `main()` 入口开始是否真的能完整跑通。

---

# 48. 捕获 main() 的输出

```python
output = io.StringIO()

with redirect_stdout(output):
    main()
```

假设 main 打印：

```text
[CodeAnalysisAgent] analyzing: ./demo_app

=== Result ===
...

=== Task Status ===
COMPLETED
```

这些内容全部进入：

```python
output
```

不会直接打印到终端。

---

# 49. `getvalue()`

```python
text = output.getvalue()
```

现在 `text` 是完整的大字符串：

```text
[CodeAnalysisAgent] analyzing: ./demo_app

=== Result ===
...

=== Task Status ===
COMPLETED
...
```

---

# 50. `assertIn`

例如：

```python
self.assertIn(
    "[CodeAnalysisAgent] analyzing: ./demo_app",
    text
)
```

意思：

> 这段文字必须出现在 text 中。

等价理解：

```python
"...字符串..." in text
```

再比如：

```python
self.assertIn(
    "=== Task Status ===\nCOMPLETED",
    text
)
```

其中：

```text
\n
```

表示换行。

所以检查的是：

```text
=== Task Status ===
COMPLETED
```

---

# 51. 为什么 `'\"potential_findings\": ['` 这样写

```python
self.assertIn(
    '"potential_findings": [',
    text
)
```

外层：

```python
'...'
```

是 Python 字符串。

里面：

```text
"potential_findings": [
```

是我们实际想搜索的文本。

因此：

```python
'"potential_findings": ['
```

实际字符串内容就是：

```text
"potential_findings": [
```

说明 main 很可能使用了 JSON 风格打印。

---

# 52. `unittest.main()` 与整个测试思路

```python
if __name__ == "__main__":
    unittest.main()
```

直接运行：

```bash
python test_runtime.py
```

时：

```python
unittest.main()
```

会自动：

```text
扫描当前文件
↓
找到 unittest.TestCase 子类
↓
找到 test_ 开头的方法
↓
逐个执行
↓
显示 PASS / FAIL
```

不需要手动调用：

```python
StateTests().test_xxx()
```

---

# 最终总图：成功路径

```text
setUp()
│
├─ 创建 AgentState
├─ 创建空 Registry
├─ 创建 Supervisor(registry)
└─ 创建 T1 并加入 state.tasks
        ↓
test_success
        ↓
创建 observation
        ↓
创建 Mock Agent
        ↓
定义 Mock Agent.run() 行为
        ↓
register
CodeAnalysisAgent → Mock Agent
        ↓
Supervisor.delegate(T1, state)
        ↓
Registry.get("CodeAnalysisAgent")
        ↓
找到 Mock Agent
        ↓
Capability Check
analyze_code ∈ [analyze_code]
        ↓
T1: PENDING → RUNNING
        ↓
MockAgent.run(T1)
        ↓
测试内部 run(T1)
        ↓
确认：
T1 是原对象
T1 已 RUNNING
Observation 尚未记录
        ↓
返回 observation
        ↓
Supervisor 收到 observation
        ↓
state.add_observation(observation)
        ↓
T1: RUNNING → COMPLETED
        ↓
return observation
        ↓
测试继续 assert：
Agent 调用次数正确
返回对象正确
State Observation 正确
Task Status 正确
Finding/Evidence 未变化
```

---

# Denied 路径

## Unknown Agent

```text
Task
↓
Supervisor
↓
Registry.get()
↓
UNKNOWN
↓
DENIED
↓
直接 return
```

## Capability 不允许

```text
Task
↓
Supervisor
↓
找到 Agent
↓
Capability 不匹配
↓
DENIED
↓
agent.run() 不得被调用
```

---

# Failure 路径

```text
Task
↓
Supervisor
↓
Capability PASS
↓
RUNNING
↓
Agent.run()
↓
抛 RuntimeError
↓
except
↓
Task = FAILED
↓
返回 FAILED
↓
不记录 Observation
```

---

# 当前测试覆盖的三条核心路径

```text
SUCCESS
DENY
FAILURE
```

这三条就是 v0.1 Runtime 的主行为。

---

# 重点语法速查表

| 代码 | 含义 |
|---|---|
| `class X(unittest.TestCase)` | 定义测试类 |
| `def setUp(self)` | 每个测试执行前初始化 |
| `self.assertEqual(a, b)` | 值相等 |
| `self.assertIs(a, b)` | 同一个对象 |
| `self.assertIsNot(a, b)` | 不是同一个对象 |
| `self.assertIsNone(x)` | x 是 None |
| `self.assertIn(a, b)` | a 在 b 中 |
| `Mock()` | 创建假对象 |
| `mock.run.side_effect = func` | 调用 run 时执行 func |
| `side_effect = Exception(...)` | 调用时抛异常 |
| `assert_called_once_with()` | 检查只调用一次且参数正确 |
| `assert_not_called()` | 检查完全没被调用 |
| `redirect_stdout()` | 截获 print |
| `io.StringIO()` | 内存字符串流 |
| `getattr(obj, name)` | 用字符串动态访问属性 |
| `with self.subTest(...)` | 循环中的独立子测试 |

---

# 最重要的工程理解

`main.py` 是：

> **正常使用系统。**

`test_runtime.py` 是：

> **故意构造不同输入，检查 Runtime 是否按照设计工作。**

以后 Runtime 会逐步升级成：

```text
Schema
↓
Workflow
↓
Capability
↓
Policy
↓
Scope
↓
HITL
↓
Execution
↓
Observation
↓
Evidence
↓
State Update
```

测试文件也会对应逐步增加：

```text
test_invalid_schema_is_rejected
test_wrong_phase_is_denied
test_policy_deny_never_executes_agent
test_out_of_scope_never_executes_agent
test_confirm_creates_pending_action
...
```

形成项目的回归测试安全网。

推荐每次 GitHub 提交前都遵循：

```text
改代码
↓
运行 tests
↓
全部 PASS
↓
git commit
```

---

# 一句话复习

你现在真正需要掌握的不是“背 unittest API”，而是：

> **测试代码负责构造输入和运行环境，Runtime 负责执行真实逻辑，断言负责检查最终行为是否符合设计。**

