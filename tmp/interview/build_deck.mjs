import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const runtime='C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1030-493-0_26.1030.493.0_x64__3k8sg7r9htsxt/dependencies';
const {Presentation,PresentationFile}=await import(pathToFileURL(runtime+'/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs'));
const skill='C:/Users/孙政/.codex/plugins/cache/openai-primary-runtime/presentations/26.1030.10813/skills/presentations';
const root='E:/security_agent';
const build=root+'/tmp/interview';
await fs.mkdir(build+'/slides',{recursive:true});
await fs.mkdir(root+'/output/presentation',{recursive:true});
const p=Presentation.create({slideSize:{width:1280,height:720}});
const font='Microsoft YaHei';
const navy='#10283F',ink='#17334A',muted='#526A7C',teal='#087F83',paper='#F7F9FB';
const content=[];
function text(s,t,x,y,w,h,size=28,color=ink,bold=false){
 const sh=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 sh.text=t;sh.text.style={typeface:font,fontSize:size,color,bold,wrap:'square',autoFit:'none',insets:0,verticalAlignment:'top'};return sh;
}
function base(title,sub='',dark=false){const s=p.slides.add();s.background.fill=dark?navy:paper;
 text(s,title,72,56,1136,84,44,dark?'#FFFFFF':ink,true);
 if(sub)text(s,sub,74,149,1120,55,24,dark?'#9EDADC':muted);
 text(s,String(p.slides.items.length).padStart(2,'0'),1165,665,45,27,17,dark?'#B5C5D0':muted);
 return s;
}
function notes(s,title,body,source){s.speakerNotes.text=body+'\n\n源码依据（当前快照 edd818c，2026-11-05）：'+source;content.push({title,notes:body,source});}
function rows(s,items,{top=225,step=108,labelW=260}={}){items.forEach(([a,b],i)=>{text(s,a,74,top+i*step,labelW,60,28,teal,true);text(s,b,74+labelW+30,top+i*step,1100-labelW-30,86,27);});}
function table(s,values,widths,top=218,height=370,size=25){
 const t=s.tables.add({rows:values.length,columns:values[0].length,left:72,top,width:1136,height,columnWidths:widths,values});
 t.borders.assign({fill:'#DAE3E9',width:1,style:'solid'});
 for(let r=0;r<values.length;r++)for(let c=0;c<values[r].length;c++){
  const cell=t.getCell(r,c);cell.fill=r===0?navy:(r%2?'#FFFFFF':'#EEF3F6');
  cell.text.style={typeface:font,fontSize:size,color:r===0?'#FFFFFF':ink,bold:r===0,insets:12,verticalAlignment:'middle'};
 }
 return t;
}
{
const s=base('Security Agent Runtime','',true);
text(s,'面向安全任务的\n受控 Agent 执行框架',74,230,1100,175,58,'#FFFFFF',true);
text(s,'v0.1 至 v0.7 七轮迭代',78,457,1050,58,31,'#9EDADC');
text(s,'安全研发 / 安全工程项目展示',78,558,1060,45,26,'#D7E3EB');
notes(s,'项目介绍','建议 30 秒。这个项目围绕一个问题展开：当模型能提出安全测试计划时，如何确保每一步执行仍然符合授权、阶段和人工审批规则？我通过七轮迭代实现了 Python Runtime，从注册和派发逐步加入安全门控、证据管理、依赖调度、分阶段规划与真实工具。当前是可运行的工程原型。','README.md；CHANGELOG.md；git log');
}
{
const s=base('项目问题与目标','安全任务需要在实际执行前落实授权边界');
rows(s,[['计划可能不可信','模型可能提出不存在的 Agent、越权目标或错误依赖。'],['审批后环境会变化','任务参数、阶段、依赖状态发生变化时，需要重新检查。'],['执行结果需要解释','源码命中、HTTP 状态和漏洞证据需要分别记录。']]);
notes(s,'项目问题与目标','建议 40 秒。传统脚本能执行工具，但当规划来自模型时，任务内容不能直接当作权限。项目把模型建议交给运行时审查，并在真正执行时再次检查。另一个目标是让结果可解释：任务执行成功，不等于漏洞被确认。项目没有业务收益或线上规模数据，因此重点展示可验证的工程行为。','runtime/plan_validator.py；runtime/supervisor.py；runtime/evidence.py');
}
{
const s=base('七轮迭代的能力积累','每一版解决一个具体的执行控制问题');
table(s,[['版本','新增能力','解决的问题'],['v0.1','Registry + Supervisor','统一注册与任务派发'],['v0.2','安全门控','阶段、能力、策略与范围限制'],['v0.3','人工审批快照','批准内容与执行内容一致'],['v0.4','Observation / Evidence / Finding','执行事实与漏洞结论分离'],['v0.5','依赖图调度','正确排序并传播上游失败'],['v0.6','分阶段规划','模型建议经过验证与编译'],['v0.7','真实工具接入','将授权落实到源码和 HTTP I/O']],[145,455,536],211,412,23);
notes(s,'七轮迭代','建议 45 秒。按版本讲设计演进，而不是逐个罗列文件。v0.1 和 v0.6 的版本归属由提交内容及现有文档对应；不是每一轮都有同名 Git tag。当前快照还包含 v0.7 的 baseline 元数据隔离与回环测试修正。','提交 757b614、92db104、39e82fd、8f27aaa、9fbba3c、9da3a73、a1406b1 至 edd818c；CHANGELOG.md');
}
{
const s=base('整体架构与职责','Planner 提议任务，Runtime 控制执行');
table(s,[['层次','核心组件','责任'],['规划','DemoPlanner / LLMPlanner','生成当前阶段的 PlanProposal'],['任务控制','Validator / Compiler / Scheduler','校验计划、分配 ID、选择就绪任务'],['执行控制','Supervisor / ApprovalStore','复检授权、审批、任务与结果绑定'],['工具执行','Agent / ToolExecutor / ToolRegistry','按动作白名单执行有限工具'],['结果管理','StateManager / Evidence / Evaluator','保存观察并按证据规则更新 Finding']],[170,475,491],220,375,24);
notes(s,'整体架构','建议 50 秒。一次调用从 build_runtime 装配开始。AgentRuntime 选择当前阶段，Planner 输出提案，Validator 校验语义，Compiler 分配 Runtime ID。Scheduler 选出就绪任务，Supervisor 检查并构造冻结请求与 ToolContext，Agent 再通过 ToolExecutor 调用真实工具。结果返回后，由 Runtime 校验身份、保存观察和更新状态。Agent 不接收全局 State。','main.py:build_runtime；runtime/orchestrator.py:run_until_blocked；runtime/supervisor.py:_execute');
}
{
const s=base('执行前的安全门控','同一任务在派发和人工批准后都要接受检查');
rows(s,[['请求是否合法','Pydantic Schema、当前阶段、Agent 注册与 capability。'],['行为是否获准','Policy 决定 ALLOW / CONFIRM / DENY；Scope 精确匹配目标。'],['任务是否可执行','Runtime 持有任务、依赖已完成、Finding 类型和目标匹配。']],{step:110});
notes(s,'执行安全门控','建议 50 秒。Capability 是 Agent 声明能完成的动作，Policy 是当前动作是否允许，Scope 是目标是否在授权范围，三者各自回答不同问题。请求的类型正确不意味着有权限。未知策略默认拒绝。直接调用 delegate 也会重查依赖和 Runtime 对象归属，不能靠绕开 Scheduler 提前执行。Scope 的实现是字符串精确相等。','runtime/supervisor.py:delegate,_check_security,_task_error；runtime/policy.py；runtime/scope.py；runtime/finding_rules.py');
}
{
const s=base('人工审批与防重放','审批绑定原 State，并保存冻结的任务快照');
rows(s,[['暂停','verify_ssrf 默认进入 WAITING_CONFIRMATION，返回 action_id。'],['批准时复检','比较参数、阶段、Finding 与依赖快照，重新检查授权。'],['恢复与防重放','执行后标记 EXECUTED；同一 Runtime 和 State 恢复调度。']]);
notes(s,'人工审批','建议 50 秒。重点用一个例子：批准前把 target 或 arguments 改掉，会导致快照不匹配而拒绝。审批还绑定创建它的 State 对象，不能把 action_id 拿到另一个 State 使用。arguments 序列化为 JSON 字符串，读取时返回新字典，dependencies 保存为 tuple。批准只解除 CONFIRM，不绕过 Policy DENY 等其他条件。当前没有用户身份认证、持久化审批或交互式 CLI 审批界面。','models/approval.py:ApprovalSnapshot；runtime/approval.py；runtime/supervisor.py:approve,_matches_snapshot；tests/test_security_regressions.py');
}
{
const s=base('任务成功与漏洞确认','独立的数据模型保留结果的含义');
table(s,[['对象','含义','示例'],['Task','工作是否执行完成','COMPLETED / FAILED / BLOCKED'],['Observation','Agent 返回的执行事实','搜索命中、响应状态、工具错误'],['Evidence','关联特定 Finding 的证据信号','错误信号 MEDIUM、布尔差异 STRONG'],['Finding','当前漏洞判断','POTENTIAL / UNCONFIRMED / CONFIRMED']],[215,420,501],228,310,25);
text(s,'当前 SQLi / SSRF 验证为教学模拟，证据规则用于展示流程。',74,574,1120,55,25,teal,true);
notes(s,'证据与结论','建议 45 秒。源码出现 execute( 只是字面命中，不证明用户输入可控。HTTP 500 也不自动等于漏洞。EvidenceExtractor 只处理关联 Finding 的 verify_sqli / verify_ssrf 成功观察。FindingEvaluator 当前规则为存在 STRONG 则 CONFIRMED，否则 UNCONFIRMED，是教学规则，不是通用漏洞判定器。v0.7 真实搜索和 HTTP baseline 都不自动生成 Finding 或 Evidence。','models/observation.py；models/evidence.py；models/finding.py；runtime/evidence.py；runtime/evaluator.py');
}
{
const s=base('依赖调度与阶段推进','ANALYZE、VERIFY、REPORT 由 Runtime 顺序推进');
rows(s,[['图校验','拒绝重复 ID、缺失依赖、自依赖、环和未来阶段依赖。'],['就绪条件','仅选择当前阶段任务，且依赖全部为 COMPLETED。'],['失败与暂停','失败传播到下游；人工审批等待会阻止阶段推进。']]);
notes(s,'调度与阶段','建议 40 秒。refresh 会反复扫描 PENDING 任务直到没有新变化，使失败沿多级依赖传播。执行目前是串行 for 循环，READY 不代表并行。PhaseManager 允许当前阶段所有任务处于终态后推进，终态包括失败，所以 COMPLETED 仅表示工作流结束，还必须看 failed_task_ids。空计划可以推进，WAITING_CONFIRMATION 不能推进。','runtime/scheduler.py；runtime/phase_manager.py；runtime/orchestrator.py');
}
{
const s=base('LLM 规划与运行时验证','结构化输出后仍然执行语义校验');
rows(s,[['限制提案','只规划当前阶段，每阶段最多 10 个任务，Runtime 分配 ID。'],['控制上下文','最多 5 条观察、50 个 Finding、30 个已完成任务 ID。'],['安全提交','完整候选任务图校验通过后，再写入 State 和规划标记。']]);
notes(s,'LLM 规划','建议 50 秒。LLMPlanner 使用结构化 PlanProposal，模型名由调用者指定。PlanValidator 检查 Agent、capability、目标、Finding 和依赖关系，PlanCompiler 把局部 key 映射为 T1 等 Runtime ID。PlanningContextBuilder 只取白名单布尔信号及受限字段，不把源码、原始响应或任意嵌套对象传入 Planner。这降低不可信内容暴露，但不能宣称彻底解决提示注入。本次验收未调用真实模型 API。','planner/llm_planner.py；runtime/plan_validator.py；runtime/plan_compiler.py；runtime/planning_context.py；runtime/orchestrator.py');
}
{
const s=base('可信 ToolContext 与双层权限','授权目录和 HTTP Origin 均来自 Runtime State');
table(s,[['Agent / Action','允许工具'],['CodeAnalysisAgent / analyze_code','search_code、read_source'],['CodeAnalysisAgent / read_file','read_source'],['VerificationAgent / check_http_baseline','controlled_http_check'],['其他组合','默认无工具权限']],[725,411],220,325,25);
text(s,'任务参数无法覆盖授权上下文；工具仍需通过参数模型校验。',74,580,1130,55,26,teal,true);
notes(s,'工具权限','建议 45 秒。第一层由 Supervisor 判断任务是否可执行，第二层由 ToolExecutor 判断这个 Agent 的这个 action 是否能用指定工具。ToolContext 是冻结模型，包含 task_id、agent、action、authorized_root、authorized_origin，由 Supervisor 在检查后创建。Agent 调用工具时只能提交业务参数。这个边界面向受控代码和不可信规划输入，并不是任意恶意 Python 插件的进程沙箱。','main.py:build_tool_executor；models/tool.py；runtime/supervisor.py:_build_tool_context；runtime/tool_executor.py:execute');
}
{
const s=base('真实源码与 HTTP 工具','限制资源范围，也限制单次执行成本');
rows(s,[['源码读取','真实路径限制在授权根目录；敏感文件名和扩展名过滤。'],['字面搜索','最多 400 个文件尝试、2000 个目录条目、16 MiB 总读取。'],['HTTP 基线','固定 Origin，GET / HEAD，禁代理与重定向，3 秒请求超时。']],{step:105});
text(s,'单文件 256 KiB；HTTP 返回计数上限 64 KiB，额外读取 1 字节探测截断。',74,586,1120,58,23,muted);
notes(s,'真实工具','建议 50 秒。读取使用 resolve(strict=True) 和 relative_to(root) 检查真实路径，同时做有界二进制读取。搜索按 casefold 做字面匹配，没有用户正则。HTTP 只接收 Origin 相对路径，拒绝协议切换、双斜杠和编码后的路径穿越。GET 实际读取上限为 64 KiB 加 1 字节用于判断截断，返回计数字段最多 64 KiB。请求超时不应描述成整个任务绝对耗时上限。目录可被其他进程并发修改的竞态与 DNS 重绑定尚未提供系统级防护。','tools/file_policy.py；tools/search_code.py；tools/read_source.py；tools/controlled_http.py');
}
{
const s=base('离线演示与实际输出','无需 API Key，现场可复现');
text(s,'.venv/Scripts/python.exe main.py --target ./tools',74,230,1120,62,29,teal,true);
table(s,[['观察项目','本次运行结果'],['工作流','COMPLETED，failed_task_ids 为空'],['任务','源码分析 T1 和报告演示 T2 均完成'],['源码搜索','扫描 6 个文件，命中 4 处 execute('],['漏洞结论','Finding 和 Evidence 均为空']],[330,806],331,255,25);
notes(s,'离线演示','建议 40 秒。命令和数字来自 2026-11-05 对当前 tools 目录的实测，不是性能基准。可先展示搜索返回的路径、行号和片段，再解释为什么没有漏洞结论。DemoPlanner 未发现 Finding 时 VERIFY 为空计划，随后进入 REPORT。即使添加 --origin，也不会让 DemoPlanner 自动创建 HTTP 任务。HTTP 的真实请求演示使用回环集成测试。','main.py；planner/demo_planner.py；本次离线命令输出；tests/test_http_loopback_integration.py');
}
{
const s=base('验证结果与安全回归','2026-11-05 当前源码快照的离线验收');
text(s,'181',74,221,330,140,112,teal,true);
text(s,'项测试通过',80,375,330,65,35,ink,true);
text(s,'审批篡改与重放\n跨目标 Finding 与未来阶段依赖\n越界读取与工具权限拒绝\n本地真实 HTTP 与非法路径零请求',470,229,725,290,31,ink);
text(s,'真实 LLM API 未启用；通过数量不等同于覆盖率或生产安全认证。',74,591,1120,50,23,muted);
notes(s,'验证结果','建议 45 秒。测试命令为 .venv/Scripts/python.exe -m unittest discover -s tests -q。本次 181 项通过，其中包含临时目录真实文件读写、SDK 离线 transport 和本地回环 HTTP。最值得展示的断言是非法路径后服务器收到的请求列表不变，以及 302 后没有请求 Location 的路径，它们验证拒绝动作没有产生网络副作用。没有声称覆盖率百分比，也没有公网扫描或真实模型调用。','tests/；tests/test_security_regressions.py；tests/test_http_loopback_integration.py；本次测试输出');
}
{
const s=base('实现中的关键取舍','将安全控制做成可检查的运行时规则');
rows(s,[['分阶段规划','阶段完成后重新规划，流程更容易验证；暂不逐观察重规划。'],['冻结请求与快照','减少共享可变对象带来的审批漂移；仍需要执行时复检。'],['内存与串行执行','降低原型复杂度；持久化恢复、并发和隔离留作后续设计。']]);
notes(s,'设计取舍','建议 40 秒。不要把未实现的特性包装成已完成。当前优先建立可以测试的控制边界。未来如果增加并发，需要处理共享状态和审批一致性；如果持久化，需要持久审批身份、幂等键及恢复协议；如果引入不可信插件，需要进程隔离和操作系统层资源限制。个人贡献应根据自己实际编写、调试和理解的部分回答，本材料不虚构团队分工。','runtime/orchestrator.py；models/approval.py；runtime/approval.py；README.md');
}
{
const s=base('当前边界与后续方向','围绕可验证能力继续扩展');
table(s,[['当前范围','后续方向（尚未实现）'],['真实源码搜索、读取和 HTTP 元信息','引入语义分析与真实漏洞验证器'],['教学 SQLi / SSRF 与报告任务','结构化漏洞报告与证据出处追踪'],['内存状态、串行阶段调度','持久化、恢复与并发一致性'],['受控 Python Agent 的应用层限制','插件进程隔离与更严格的 I/O 边界']],[568,568],225,342,25);
notes(s,'边界与后续','建议 30 秒。明确当前价值在执行安全框架和可回归验证的控制逻辑。真实工具已经接入，但报告与漏洞验证仍然是教学实现。下一步可以先补充有来源标记的证据和真实验证插件，再考虑持久化与并发。这样的顺序有利于保持安全边界清晰。','README.md；agents/verification.py；agents/report.py；runtime/evaluator.py');
}
{
const s=base('面试讨论','',true);
text(s,'如何证明一次执行\n确实符合授权？',74,220,1100,175,60,'#FFFFFF',true);
text(s,'任务校验和执行复检\n审批快照与状态绑定\n工具边界和拒绝路径测试',78,440,1080,170,31,'#9EDADC');
notes(s,'面试讨论','建议 15 秒收束。可以选择审批快照、依赖失败传播或真实 HTTP 的拒绝路径测试进行源码展开。若被问是否独立完成，应如实说明自己的设计、实现、测试与 AI 辅助范围，重点解释能够复现的关键行为。','runtime/supervisor.py；tests/test_security_regressions.py；tests/test_http_loopback_integration.py');
}
await fs.writeFile(build+'/deck_content.json',JSON.stringify(content,null,2));
await (await PresentationFile.exportPptx(p)).save(build+'/candidate.pptx');
for(let i=0;i<p.slides.items.length;i++){
 const blob=await p.export({slide:p.slides.items[i],format:'png',scale:1});
 await fs.writeFile(build+`/slides/slide-${String(i+1).padStart(2,'0')}.png`,new Uint8Array(await blob.arrayBuffer()));
}
const {finalizePresentation}=await import(pathToFileURL(skill+'/container_tools/artifact_tool_utils.mjs'));
const result=await finalizePresentation({workspaceDir:root,candidatePath:build+'/candidate.pptx',finalPath:root+'/output/presentation/Security_Agent_面试展示_v0.1-v0.7.pptx',pythonExecutable:runtime+'/python/python.exe',integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,receiptPath:build+'/deck.validation.json'});
console.log(JSON.stringify(result));
