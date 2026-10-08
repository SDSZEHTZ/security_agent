from pydantic import ValidationError

from runtime.approval import ApprovalStore
from runtime.evidence import EvidenceExtractor
from runtime.evaluator import FindingEvaluator
from runtime.policy import PolicyEngine
from runtime.scope import ScopeEngine
from runtime.state_manager import StateManager
from runtime.validator import (
    ObservationValidator,
    RequestValidator,
)
from runtime.workflow import WorkflowEngine

class Supervisor:

    def __init__(
        self,
        registry,
        validator=None,
        observation_validator=None,
        workflow=None,
        policy=None,
        scope=None,
        approval_store=None,
        state_manager=None,
        evidence_extractor=None,
        finding_evaluator=None,
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

        self.observation_validator = (
            observation_validator
            or ObservationValidator()
        )

        self.state_manager = (
            state_manager
            or StateManager()
        )

        self.evidence_extractor = (
            evidence_extractor
            or EvidenceExtractor()
        )

        self.finding_evaluator = (
            finding_evaluator
            or FindingEvaluator()
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

            self.state_manager.update_task_status(
                state,
                task.id,
                "WAITING_CONFIRMATION",
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
            self.state_manager.find_task(
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

            self.state_manager.update_task_status(
                state,
                state_task.id,
                "BLOCKED",
            )

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

            self.state_manager.update_task_status(
                state,
                state_task.id,
                "BLOCKED",
            )

            self.approval_store.mark_rejected(
                action_id
            )

            return {
                "status": "DENIED",
                "reason": decision["reason"],
            }

        if (
            state_task.finding_id is not None
            and self.state_manager.find_finding(
                state,
                state_task.finding_id,
            )
            is None
        ):

            self.state_manager.update_task_status(
                state,
                state_task.id,
                "BLOCKED",
            )

            self.approval_store.mark_rejected(
                action_id
            )

            return {
                "status": "DENIED",
                "reason": "UNKNOWN_FINDING",
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

        finding = None

        if state_task.finding_id is not None:

            finding = self.state_manager.find_finding(
                state,
                state_task.finding_id,
            )

            if finding is None:

                self.state_manager.update_task_status(
                    state,
                    state_task.id,
                    "FAILED",
                )

                return {
                    "status": "FAILED",
                    "reason": "UNKNOWN_FINDING",
                }

        self.state_manager.update_task_status(
            state,
            state_task.id,
            "RUNNING",
        )

        try:

            result = agent_info[
                "instance"
            ].run(
                execution_task
            )

        except Exception as exc:

            self.state_manager.update_task_status(
                state,
                state_task.id,
                "FAILED",
            )

            return {
                "status": "FAILED",
                "reason": str(exc),
            }

        try:

            observation = (
                self.observation_validator
                .validate(result)
            )

        except ValidationError as exc:

            self.state_manager.update_task_status(
                state,
                state_task.id,
                "FAILED",
            )

            return {
                "status": "FAILED",
                "reason": "INVALID_OBSERVATION",
                "errors": exc.errors(),
            }

        if (
            observation.agent
            != execution_task.agent
            or observation.task_id
            != execution_task.id
        ):

            self.state_manager.update_task_status(
                state,
                state_task.id,
                "FAILED",
            )

            return {
                "status": "FAILED",
                "reason": "OBSERVATION_MISMATCH",
            }

        self.state_manager.add_observation(
            state,
            observation,
        )

        if observation.execution_status != "SUCCESS":

            self.state_manager.update_task_status(
                state,
                state_task.id,
                observation.execution_status,
            )

            return observation

        evidence_list = (
            self.evidence_extractor.extract(
                observation,
                state_task,
            )
        )

        for evidence in evidence_list:

            self.state_manager.add_evidence(
                state,
                evidence,
            )

        if finding is not None:

            new_status = (
                self.finding_evaluator.evaluate(
                    finding,
                    state.evidence,
                )
            )

            self.state_manager.update_finding_status(
                state,
                finding.id,
                new_status,
            )

        self.state_manager.update_task_status(
            state,
            state_task.id,
            "COMPLETED",
        )

        return observation


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
            and task.finding_id == snapshot.finding_id
        )
