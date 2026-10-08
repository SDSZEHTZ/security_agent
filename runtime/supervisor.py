from pydantic import ValidationError

from runtime.approval import ApprovalStore
from runtime.policy import PolicyEngine
from runtime.scope import ScopeEngine
from runtime.validator import RequestValidator
from runtime.workflow import WorkflowEngine


class Supervisor:

    def __init__(
        self,
        registry,
        validator=None,
        workflow=None,
        policy=None,
        scope=None,
        approval_store=None,
    ):

        self.registry = registry

        self.validator = (
            validator or RequestValidator()
        )

        self.workflow = (
            workflow or WorkflowEngine()
        )

        self.policy = (
            policy or PolicyEngine()
        )

        self.scope = (
            scope or ScopeEngine()
        )

        self.approval_store = (
            approval_store
            or ApprovalStore()
        )


    def delegate(self, task, state):

        try:

            request = (
                self.validator.validate(
                    task
                )
            )

        except ValidationError as exc:

            return {
                "status": "DENIED",
                "reason": "INVALID_SCHEMA",
                "errors": exc.errors(),
            }

        decision = self._check_security(
            request,
            state,
            approval_granted=False,
        )

        if decision["decision"] == "DENY":

            return {
                "status": "DENIED",
                "reason": decision["reason"],
            }

        if (
            decision["decision"]
            == "CONFIRM"
        ):

            pending = (
                self.approval_store.create(
                    task
                )
            )

            task.status = (
                "WAITING_CONFIRMATION"
            )

            return {
                "status":
                    "WAITING_CONFIRMATION",

                "reason":
                    "POLICY_CONFIRM",

                "action_id":
                    pending.action_id,
            }

        return self._execute(
            execution_task=task,
            state_task=task,
            state=state,
            agent_info=decision[
                "agent_info"
            ],
        )


    def approve(
        self,
        action_id,
        state,
    ):

        pending = (
            self.approval_store.get(
                action_id
            )
        )

        if pending is None:

            return {
                "status": "DENIED",
                "reason":
                    "UNKNOWN_PENDING_ACTION",
            }

        if (
            pending.status
            != "WAITING_CONFIRMATION"
        ):

            return {
                "status": "DENIED",
                "reason":
                    "INVALID_APPROVAL_STATE",
            }

        pending = (
            self.approval_store.approve(
                action_id
            )
        )

        snapshot = pending.snapshot

        state_task = (
            self._find_state_task(
                state,
                snapshot.id,
            )
        )

        if state_task is None:

            self.approval_store.mark_rejected(
                action_id
            )

            return {
                "status": "DENIED",
                "reason": "TASK_NOT_FOUND",
            }

        if not self._matches_snapshot(
            state_task,
            snapshot,
        ):

            state_task.status = "BLOCKED"

            self.approval_store.mark_rejected(
                action_id
            )

            return {
                "status": "DENIED",
                "reason":
                    "APPROVED_REQUEST_MISMATCH",
            }

        request = (
            self.validator.validate(
                snapshot
            )
        )

        decision = self._check_security(
            request,
            state,
            approval_granted=True,
        )

        if decision["decision"] == "DENY":

            state_task.status = "BLOCKED"

            self.approval_store.mark_rejected(
                action_id
            )

            return {
                "status": "DENIED",
                "reason": decision["reason"],
            }

        result = self._execute(
            execution_task=snapshot,
            state_task=state_task,
            state=state,
            agent_info=decision[
                "agent_info"
            ],
        )

        self.approval_store.mark_executed(
            action_id
        )

        return result


    def _check_security(
        self,
        request,
        state,
        approval_granted,
    ):

        # Workflow
        if not self.workflow.is_allowed(
            state.phase,
            request.action,
        ):

            return {
                "decision": "DENY",
                "reason":
                    "ACTION_NOT_ALLOWED_IN_PHASE",
            }

        # Registry
        agent_info = self.registry.get(
            request.agent
        )

        if agent_info is None:

            return {
                "decision": "DENY",
                "reason": "UNKNOWN_AGENT",
            }

        # Capability
        if request.action not in (
            agent_info["capabilities"]
        ):

            return {
                "decision": "DENY",
                "reason":
                    "CAPABILITY_NOT_ALLOWED",
            }

        # Policy
        policy_decision = (
            self.policy.evaluate(
                request.action
            )
        )

        if policy_decision == "DENY":

            return {
                "decision": "DENY",
                "reason": "POLICY_DENIED",
            }

        if policy_decision not in {
            "ALLOW",
            "CONFIRM",
        }:

            return {
                "decision": "DENY",
                "reason": "POLICY_DENIED",
            }

        # Scope
        if not self.scope.is_allowed(
            request.target,
            state.target,
        ):

            return {
                "decision": "DENY",
                "reason":
                    "TARGET_OUT_OF_SCOPE",
            }

        # HITL
        if (
            policy_decision == "CONFIRM"
            and not approval_granted
        ):

            return {
                "decision": "CONFIRM",
                "agent_info": agent_info,
            }

        return {
            "decision": "ALLOW",
            "agent_info": agent_info,
        }


    def _execute(
        self,
        execution_task,
        state_task,
        state,
        agent_info,
    ):

        state_task.status = "RUNNING"

        try:

            result = agent_info[
                "instance"
            ].run(
                execution_task
            )

        except Exception as exc:

            state_task.status = "FAILED"

            return {
                "status": "FAILED",
                "reason": str(exc),
            }

        state.add_observation(result)

        state_task.status = "COMPLETED"

        return result


    def _find_state_task(
        self,
        state,
        task_id,
    ):

        for task in state.tasks:

            if task.id == task_id:
                return task

        return None


    def _matches_snapshot(
        self,
        task,
        snapshot,
    ):

        return (
            task.id == snapshot.id
            and task.agent == snapshot.agent
            and task.action == snapshot.action
            and task.target == snapshot.target
        )
