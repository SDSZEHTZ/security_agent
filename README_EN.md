# Security Agent Runtime v0.6

A phase-planned runtime that preserves the existing Registry, Scheduler,
Supervisor, Evidence and HITL layers.

```text
Goal → Planner → PlanProposal → Validator → Compiler → Runtime Tasks
     → Scheduler → Supervisor → Agent → Observation / Evidence / Finding
     → Plan the next runtime-selected phase
```

The runtime owns ANALYZE → VERIFY → REPORT → END. The planner proposes at most
10 tasks per phase and cannot choose permissions, runtime IDs or mutate state.

## Run

Python 3.10+:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe main.py
```

The default DemoPlanner is offline. For real LLM planning:

```powershell
$env:OPENAI_API_KEY = "<your-api-key>"
.venv/Scripts/python.exe main.py --model "<structured-output-capable-model>" --target "./demo_app"
```

All agents remain mocks, including ReportAgent. They do not inspect files, send
verification requests or execute commands. The CLI renders authoritative runtime
findings and evidence. A real planner does not make this a real security scanner.

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

Unit tests use injected clients and planners without network calls. Live API tests
are separately opt-in and may incur cost:

```powershell
$env:RUN_LLM_INTEGRATION = "1"
$env:OPENAI_MODEL = "<structured-output-capable-model>"
.venv/Scripts/python.exe -m unittest discover -s integration_tests -v
```

See [Chinese documentation](README.md) and [audit notes](AUDIT_v0.6.md).
