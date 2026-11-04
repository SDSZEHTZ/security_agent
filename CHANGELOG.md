## v0.6.0 - LLM Planning and Re-planning

### Added

- Structured LLM plan proposals
- Pydantic plan schema
- Runtime-owned task ID allocation
- Plan semantic validation
- Phase-aware task scheduling
- Planning context builder
- LLM planner adapter
- Phase-level dynamic re-planning
- Runtime orchestrator

### Security

- LLM plans cannot directly mutate runtime state
- Workflow phase remains runtime-controlled
- Invalid agents, capabilities, dependencies and targets are rejected
- LLM-generated plans are revalidated before execution
- Observation content is treated as untrusted planning context
- Execution authorization remains independent of planner decisions

### Completed and audited

- Corrected misplaced planner/compiler implementations and StateManager methods
- Added bounded Responses API planner with injectable client and explicit error handling
- Connected runtime-created potential findings, phase re-planning and mock report tasks
- Kept an offline demo entry point; real LLM planning requires an explicit model
- Added phase/dependency checks at scheduling and execution time
- Bound approvals to their original state and snapshotted phase/dependencies
- Rejected repeated dispatch, mismatched findings and verification of terminal findings
- Passed frozen requests to agents instead of mutable runtime tasks
- Handled TIMEOUT as a terminal failure and validated graphs before committing plans
- Whitelisted planning-context signals instead of forwarding arbitrary observation data
- Added deterministic planning/security regressions, offline SDK transport tests,
  and separately opt-in live API integration tests
- Updated Chinese/English usage documentation and recorded audit scope/limitations
