from types import SimpleNamespace

from planner.llm_planner import PlannerError
from runtime.plan_validator import PlanValidationError
from runtime.scheduler import TaskGraphError


class AgentRuntime:
    def __init__(
        self, planner, supervisor, scheduler, plan_validator, plan_compiler,
        context_builder, phase_manager, state_manager, registry,
    ):
        self.planner = planner
        self.supervisor = supervisor
        self.scheduler = scheduler
        self.plan_validator = plan_validator
        self.plan_compiler = plan_compiler
        self.context_builder = context_builder
        self.phase_manager = phase_manager
        self.state_manager = state_manager
        self.registry = registry

    def run_until_blocked(self, goal, state):
        if state.phase not in {*self.phase_manager.PHASES, "END"}:
            return {"status": "BLOCKED", "reason": "INVALID_RUNTIME_PHASE"}
        while state.phase != "END":
            try:
                self.scheduler.validate_graph(state)
                if state.phase not in state.planned_phases:
                    context = self.context_builder.build(state, self.registry)
                    proposal = self.planner.plan_phase(
                        goal=goal, phase=state.phase, context=context,
                    )
                    self.plan_validator.validate(
                        proposal=proposal, expected_phase=state.phase,
                        state=state, registry=self.registry,
                    )
                    new_tasks = self.plan_compiler.compile(proposal, state)
                    # Validate before committing any tasks or the planned marker.
                    self.scheduler.validate_graph(
                        SimpleNamespace(tasks=[*state.tasks, *new_tasks])
                    )
                    for task in new_tasks:
                        self.state_manager.add_task(state, task)
                    self.state_manager.mark_phase_planned(state, state.phase)
            except (PlannerError, PlanValidationError, TaskGraphError) as exc:
                return {"status": "BLOCKED", "reason": str(exc), "phase": state.phase}

            if not self._run_ready_tasks(state):
                return {"status": "BLOCKED", "reason": "NO_EXECUTION_PROGRESS"}

            waiting = [
                task.id for task in state.tasks
                if task.phase == state.phase and task.status == "WAITING_CONFIRMATION"
            ]
            if waiting:
                actions = [
                    pending.action_id
                    for pending in self.supervisor.approval_store.actions.values()
                    if pending.snapshot.id in waiting
                    and pending.status == "WAITING_CONFIRMATION"
                    and self.supervisor.approval_store.belongs_to(pending.action_id, state)
                ]
                return {
                    "status": "WAITING_CONFIRMATION",
                    "task_ids": waiting, "action_ids": actions,
                }
            if not self.phase_manager.can_advance(state):
                return {"status": "BLOCKED", "phase": state.phase}
            self.state_manager.update_phase(
                state, self.phase_manager.next_phase(state.phase),
            )

        # Completion means the workflow ended, not that all tasks succeeded.
        return {
            "status": "COMPLETED",
            "failed_task_ids": [
                task.id for task in state.tasks
                if task.status in {"FAILED", "BLOCKED", "TIMEOUT"}
            ],
        }

    def _run_ready_tasks(self, state):
        while True:
            self.scheduler.refresh(state)
            ready = self.scheduler.ready_tasks(state)
            if not ready:
                return True
            before = [(task.id, task.status) for task in ready]
            for task in ready:
                self.supervisor.delegate(task, state)
            if before == [(task.id, task.status) for task in ready]:
                return False
