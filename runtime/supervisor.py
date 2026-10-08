from pydantic import ValidationError

from runtime.validator import RequestValidator
from runtime.workflow import WorkflowEngine
from runtime.policy import PolicyEngine
from runtime.scope import ScopeEngine


class Supervisor:

    def __init__(
        self,
        registry,
        validator=None,
        workflow=None,
        policy=None,
        scope=None,
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

    def delegate(self, task, state):

        # 1. Schema Validation
        try:                                                                            
            request = self.validator.validate(
                task
            )

        except ValidationError as exc:

            return {
                "status": "DENIED",
                "reason": "INVALID_SCHEMA",
                "errors": exc.errors(),
            }

        # 2. Workflow Check
        if not self.workflow.is_allowed(
            state.phase,
            request.action,
        ):

            return {
                "status": "DENIED",
                "reason": "ACTION_NOT_ALLOWED_IN_PHASE",
            }

        # 3. Agent Lookup
        agent_info = self.registry.get(
            request.agent
        )

        if agent_info is None:

            return {
                "status": "DENIED",
                "reason": "UNKNOWN_AGENT",
            }

        # 4. Capability Check
        if request.action not in agent_info[
            "capabilities"
        ]:

            return {
                "status": "DENIED",
                "reason": "CAPABILITY_NOT_ALLOWED",
            }

        # 5. Policy
        policy_decision = (
            self.policy.evaluate(
                request.action
            )
        )

        if policy_decision == "DENY":

            return {
                "status": "DENIED",
                "reason": "POLICY_DENIED",
            }

        # 6. Scope
        if not self.scope.is_allowed(
            request.target,
            state.target,
        ):

            return {
                "status": "DENIED",
                "reason": "TARGET_OUT_OF_SCOPE",
            }

        # 7. HITL Gate
        if policy_decision == "CONFIRM":

            return {
                "status": "WAITING_CONFIRMATION",
                "reason": "POLICY_CONFIRM",
            }

        # 8. Execution
        task.status = "RUNNING"

        try:

            result = agent_info[
                "instance"
            ].run(task)

        except Exception as exc:

            task.status = "FAILED"

            return {
                "status": "FAILED",
                "reason": str(exc),
            }

        # 9. Observation
        state.add_observation(result)

        # 10. Complete
        task.status = "COMPLETED"

        return result