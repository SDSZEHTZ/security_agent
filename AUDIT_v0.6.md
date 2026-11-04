# v0.6 代码审计与修复记录

日期：2026-11-04。范围：仓库 Python 运行代码、现有测试与 v0.6 新增模块。
未进行外部目标扫描，也未使用真实模型产生计划。

## 基线

修改前有 49 项单元测试，其中 39 项因 AgentState.add_task 缺失而报错。
已存在的 v0.6 未提交工作予以保留并补齐，未调整主要架构或创建新分支。

## 已修复

| 优先级 | 问题 | 修复及验证 |
| --- | --- | --- |
| 高 | llm_planner.py、plan_compiler.py 内容错位，包初始化文件名称错误 | 恢复正确模块，补齐注入客户端的 Responses Planner；结构化调用和失败路径有离线测试 |
| 高 | StateManager 新增函数位于类外，旧 State 接口被删除 | 方法归类；旧 add_task 作为 StateManager 兼容入口 |
| 高 | 当前阶段之外的任务进入 READY，直接派发也缺少 Task Phase 校验 | Scheduler 和 Supervisor 双层检查；拒绝未来阶段依赖和未知阶段 |
| 高 | 同一任务重复派发可以创建两份审批并执行两次 | 状态约束、防重派发、审批绑定 State；phase/dependencies 纳入快照并二次校验 |
| 高 | Finding 仅检查 ID 存在，SQLi 证据可确认另一目标的 SSRF | 规划与执行共用目标、类型、终态检查，执行时再次授权 |
| 中 | TIMEOUT 既不阻断依赖也不被视作阶段终态 | 超时传播为下游 BLOCKED，允许当前阶段结束 |
| 中 | 分析结果不能产生下一阶段可引用的 Finding | Runtime 对已知信号分配 Finding ID、固定 POTENTIAL 状态并去重 |
| 中 | Agent 得到可变 Runtime Task | 普通执行和审批执行均传入冻结请求 |
| 中 | 规划上下文复制任意 Observation 字段 | 改为信号白名单与列表上限，不传原始响应或嵌套数据 |
| 中 | 任务图失败前已写 State、标记 planned | 先验证候选完整图，再提交任务和标记；增加失败不污染 State 的回归 |
| 中 | main 仍硬编码旧验证任务，缺少 REPORT 接线和 v0.6 测试 | main 负责组装/输入/输出，离线与真实 Planner 可替换；增加 Mock 报告阶段 |
| 中 | 已终结 Finding 被再次评估可能触发非法状态转换 | 在 Agent 执行前拒绝再次验证终结 Finding |
| 低 | 文档仍描述 v0.1，无真实 API 测试隔离 | 更新双语 README、运行说明、手动启用的 integration_tests |

## 验证口径

- 最终结果：项目虚拟环境下 80 项离线测试通过；真实 API 集成测试按默认配置跳过 1 项。
- 离线 CLI 三阶段运行通过；缺少 API Key 时真实模式在创建客户端前退出；pip check 通过。
- 验证环境：Python 3.10.9、Pydantic 2.13.5、OpenAI SDK 2.54.0；已安装声明的虚拟环境依赖。
- 原有安全测试保留；VERIFY 任务显式声明 phase，成功派发测试改为验证冻结请求。
- 新增测试覆盖 Proposal/DAG、动态阶段上下文、空计划、审批恢复、拒绝与异常路径。
- 使用真实 OpenAI SDK 的本地 Mock HTTP 传输验证结构化解析，可测试 SDK 行为而不联网。
- 真实模型的质量、账户权限和网络可用性不由离线测试证明；API 集成测试单独开启。
- 本次没有做第三方依赖 CVE 数据库扫描，也不宣称代码不存在其他漏洞。

## 保留的边界

1. Agent 仍为 Mock；报告任务为演示，控制台打印 Runtime 结果。固定演示数据不是实际漏洞证据。
2. Scope 仍精确比较目标字符串。接入真实文件/HTTP 工具之前，需在工具层处理路径规范化、
   符号链接、重定向、DNS 与实际访问目标；本次没有扩大授权范围。
3. Runtime 为同步、单进程、内存状态。未引入并发锁、持久化、崩溃恢复或审批撤销界面。
   TIMEOUT 支持的是 Agent 返回的终态，不是对任意阻塞 Agent 的强制中断。
4. Python 冻结模型防止正常字段赋值，不是进程沙箱；注册的 Python Agent 实现必须受信任。
   EvidenceExtractor 仍信任 Agent 上报的验证信号，未引入独立工具证明链。
5. Finding 只支持 SQL Injection / SSRF，按目标和类型去重；不区分同类型漏洞的不同源码位置。
6. 上下文裁剪和提示词不能彻底消除 Prompt Injection。真正权限边界仍是 Validator 与 Supervisor。
7. 保留旧手动验证接口无 finding_id 的用法，执行不产生关联证据；
   LLM Proposal 中的验证任务则强制要求有效 Finding。
8. 失败/阻断的阶段任务仍允许进入下一阶段以便报告；最终返回 failed_task_ids，
   不能把 Workflow COMPLETED 等同于安全审计成功。
