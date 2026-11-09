# Security Agent Runtime v0.7

A phase-planned runtime that preserves the existing Registry, Scheduler,
Supervisor, Evidence and HITL layers, with real source tools and controlled HTTP baselines.

```text
Goal → Planner → PlanProposal → Validator → Compiler → Runtime Tasks
     → Scheduler → Supervisor → ToolContext → Agent → ToolExecutor → Tool
     → Observation / Evidence / Finding
     → Plan the next runtime-selected phase
```

The runtime owns ANALYZE → VERIFY → REPORT → END. The planner proposes at most
10 tasks per phase and cannot choose permissions, runtime IDs or mutate state.

## Run

Python 3.10+:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe main.py --target .
```

The default DemoPlanner is offline and searches for `execute(` in the authorized
source directory. Search hits do not create findings or evidence. The demo then
runs the mock report task, without automatically scheduling verification.
Use an existing source directory. The bundled, harmless `./demo_app` fixture is the
default target, so `python main.py` also works without arguments.

To authorize an HTTP origin separately from the source directory:

```powershell
.venv/Scripts/python.exe main.py --target . --origin http://127.0.0.1:5000
```

This only sets authorization; DemoPlanner does not automatically schedule HTTP tasks.
The VERIFY action `check_http_baseline` defaults to `HEAD /`, permits GET/HEAD and
origin-relative paths, disables redirects and proxies, and uses a 3-second request
timeout and 64 KiB response read limit. A baseline is an observation, not proof of a vulnerability.

For real LLM planning:

```powershell
$env:OPENAI_API_KEY = "<your-api-key>"
.venv/Scripts/python.exe main.py --model "<structured-output-capable-model>" --target . --goal "Search source using analyze_code with query execute("
```

CodeAnalysisAgent now calls search_code/read_source, and HTTP baseline uses a real tool.
SQLi/SSRF verification and ReportAgent remain teaching demos. No system commands are
executed. Built-in simulated verification results carry `verification_mode=DEMO_FIXTURE`.
EvidenceExtractor ignores them; planner context retains only the simulation marker,
without fabricated response codes or vulnerability signals. Completing a demo task
does not establish a vulnerability. The marker prevents accidental misuse, but is
not proof of trustworthy third-party agent output. The CLI renders runtime findings
and evidence.

Task arguments: analyze_code requires a string query and accepts max_matches (agent
default 20); read_file requires a relative path; check_http_baseline accepts path/method.
Planner tool awareness and source feedback are deferred; specify required arguments
in the goal when using the LLM planner.

LLMPlanner uses Responses API structured parsing with PlanProposal, request
timeout/retry/output limits and store=False. Refusals, incomplete responses and
API failures stop planning without committing a phase.
See [official documentation](https://developers.openai.com/api/docs/guides/structured-outputs).

## Controls

- Validate schema, phase, capabilities, exact target, finding relationships and DAG.
- Allocate runtime IDs and validate the combined graph before committing the plan.
- Schedule only the current phase; block dependents on failure, denial or timeout.
- Recheck authorization, task ownership, phase and dependencies before execution.
- Bind approvals to the original state and immutable request, including phase and
  dependencies. Repeated dispatch and approval replay are denied.
- Pass frozen requests to agents; never give planners global state.
- Supervisor creates frozen ToolContext after authorization, using State for the
  source root and HTTP origin. Task arguments cannot override them. This is a
  planner trust boundary, not process isolation for arbitrary Python agent code.
- Check agent capabilities and tool permissions separately. Analysis may search/read;
  read_file may only read; baseline may only use HTTP. Other pairs have no tool access.
- Map expected tool argument/permission failures and execution ERROR to FAILED
  observations/tasks. Tool timeouts also map to FAILED in this version.
- Build a bounded planning context from whitelisted observation signals, findings
  and completed IDs. Raw responses, source and arbitrary nested data are excluded.
- Runtime creates and deduplicates POTENTIAL findings from recognized analysis
  signals. Planned verification requires a matching unresolved finding.
- Empty phases advance. Pending approvals pause progression. Resume does not
  replan completed/planned phases.

COMPLETED means workflow termination, not universal task success or vulnerability
confirmation. Check failed_task_ids. CLI exits successfully only when it is empty.

For HITL, keep the same runtime/state, present returned action_ids to the user,
call runtime.supervisor.approve(action_id, state) only after explicit approval,
then run_until_blocked(goal, state) again. The CLI has no interactive approval UI
or persistent storage.

## Test

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Tests use injected clients and planners plus a temporary HTTP server on 127.0.0.1
for real loopback requests; they do not access the public internet. Live API tests
are separately opt-in and may incur cost:

```powershell
$env:RUN_LLM_INTEGRATION = "1"
$env:OPENAI_MODEL = "<structured-output-capable-model>"
.venv/Scripts/python.exe -m unittest discover -s integration_tests -v
```

See [Chinese documentation](README.md) and [audit notes](AUDIT_v0.6.md).

HTTP baseline observations store response metadata under `Observation.data["http_baseline"]`; this is not vulnerability evidence.
