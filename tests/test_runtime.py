import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock

from agents.code_analysis import CodeAnalysisAgent
from agents.verification import VerificationAgent
from main import main
from models.task import Task
from runtime.registry import AgentRegistry
from runtime.supervisor import Supervisor
from state import AgentState


class StateTests(unittest.TestCase):
    def test_task_defaults_to_pending(self):
        task = Task("T1", "CodeAnalysisAgent", "analyze_code", "./demo_app")
        self.assertEqual(task.status, "PENDING")

    def test_state_defaults_and_mutations(self):
        state = AgentState("./demo_app")
        task = Task("T1", "CodeAnalysisAgent", "analyze_code", state.target)
        observation = {"task_id": task.id}

        self.assertEqual(state.target, "./demo_app")
        self.assertEqual(state.phase, "ANALYZE")
        self.assertEqual(state.tasks, [])
        self.assertEqual(state.observations, [])
        self.assertEqual(state.findings, [])
        self.assertEqual(state.evidence, [])

        state.add_task(task)
        state.add_observation(observation)
        self.assertIs(state.tasks[0], task)
        self.assertIs(state.observations[0], observation)

    def test_state_collections_are_not_shared(self):
        first = AgentState("./first")
        second = AgentState("./second")
        for name in ("tasks", "findings", "evidence", "observations"):
            with self.subTest(collection=name):
                self.assertIsNot(getattr(first, name), getattr(second, name))


class RegistryTests(unittest.TestCase):
    def test_registration_and_lookup(self):
        registry = AgentRegistry()
        agent = CodeAnalysisAgent()
        registry.register("CodeAnalysisAgent", agent, ["analyze_code"])

        info = registry.get("CodeAnalysisAgent")
        self.assertIs(info["instance"], agent)
        self.assertEqual(info["capabilities"], ["analyze_code"])

    def test_unknown_agent_returns_none(self):
        self.assertIsNone(AgentRegistry().get("UnknownAgent"))

    def test_registration_copies_capabilities(self):
        registry = AgentRegistry()
        capabilities = ["analyze_code"]
        registry.register("CodeAnalysisAgent", CodeAnalysisAgent(), capabilities)
        capabilities.append("verify_sqli")
        self.assertEqual(
            registry.get("CodeAnalysisAgent")["capabilities"], ["analyze_code"]
        )


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.state = AgentState("./demo_app")
        self.registry = AgentRegistry()
        self.supervisor = Supervisor(self.registry)
        self.task = Task("T1", "CodeAnalysisAgent", "analyze_code", self.state.target)
        self.state.add_task(self.task)

    def test_success_records_observation_and_completes_task(self):
        observation = {
            "agent": "CodeAnalysisAgent",
            "task_id": "T1",
            "execution_status": "SUCCESS",
            "data": {},
        }

        def run(task):
            self.assertIs(task, self.task)
            self.assertEqual(task.status, "RUNNING")
            self.assertEqual(self.state.observations, [])
            return observation

        agent = Mock()
        agent.run.side_effect = run
        self.registry.register(self.task.agent, agent, [self.task.action])

        result = self.supervisor.delegate(self.task, self.state)

        agent.run.assert_called_once_with(self.task)
        self.assertIs(result, observation)
        self.assertIs(self.state.observations[0], observation)
        self.assertEqual(self.task.status, "COMPLETED")
        self.assertEqual(self.state.tasks, [self.task])
        self.assertEqual(self.state.tasks[0].status, "COMPLETED")
        self.assertEqual(self.state.findings, [])
        self.assertEqual(self.state.evidence, [])

    def test_unknown_agent_is_denied(self):
        result = self.supervisor.delegate(self.task, self.state)

        self.assertEqual(result, {"status": "DENIED", "reason": "UNKNOWN_AGENT"})
        self.assertEqual(self.task.status, "PENDING")
        self.assertEqual(self.state.observations, [])

    def test_unsupported_capability_is_denied_without_running_agent(self):
        agent = Mock()
        self.registry.register(self.task.agent, agent, ["verify_sqli"])

        result = self.supervisor.delegate(self.task, self.state)

        self.assertEqual(
            result, {"status": "DENIED", "reason": "CAPABILITY_NOT_ALLOWED"}
        )
        agent.run.assert_not_called()
        self.assertEqual(self.task.status, "PENDING")
        self.assertEqual(self.state.observations, [])

    def test_agent_exception_marks_task_failed(self):
        agent = Mock()
        agent.run.side_effect = RuntimeError("Mock execution failed")
        self.registry.register(self.task.agent, agent, [self.task.action])

        result = self.supervisor.delegate(self.task, self.state)

        self.assertEqual(
            result, {"status": "FAILED", "reason": "Mock execution failed"}
        )
        self.assertEqual(self.task.status, "FAILED")
        self.assertEqual(self.state.observations, [])

    def test_both_mock_agents_run_through_runtime(self):
        self.registry.register("CodeAnalysisAgent", CodeAnalysisAgent(), ["analyze_code"])
        self.registry.register("VerificationAgent", VerificationAgent(), ["verify_sqli"])
        verification = Task("T2", "VerificationAgent", "verify_sqli", self.state.target)
        self.state.add_task(verification)

        with redirect_stdout(io.StringIO()):
            analysis_result = self.supervisor.delegate(self.task, self.state)
            self.state.phase = "VERIFY"
            verification_result = self.supervisor.delegate(verification, self.state)

        self.assertEqual(analysis_result["agent"], "CodeAnalysisAgent")
        self.assertEqual(analysis_result["task_id"], "T1")
        self.assertEqual(analysis_result["execution_status"], "SUCCESS")
        self.assertEqual(
            analysis_result["data"]["potential_findings"], ["SQL Injection"]
        )
        self.assertEqual(verification_result["agent"], "VerificationAgent")
        self.assertEqual(verification_result["task_id"], "T2")
        self.assertEqual(verification_result["execution_status"], "SUCCESS")
        self.assertEqual(self.task.status, "COMPLETED")
        self.assertEqual(verification.status, "COMPLETED")
        self.assertEqual(
            self.state.observations, [analysis_result, verification_result]
        )
        self.assertEqual(self.state.findings, [])
        self.assertEqual(self.state.evidence, [])


class SecurityControlTests(unittest.TestCase):
    def setUp(self):
        self.state = AgentState("./demo_app")
        self.registry = AgentRegistry()
        self.supervisor = Supervisor(self.registry)

    def test_invalid_action_schema_is_denied(self):
        self.registry.get = Mock(wraps=self.registry.get)
        task = Task(
            "T1",
            "CodeAnalysisAgent",
            "destroy_everything",
            self.state.target,
        )

        result = self.supervisor.delegate(task, self.state)

        self.assertEqual(result["status"], "DENIED")
        self.assertEqual(result["reason"], "INVALID_SCHEMA")
        self.assertIn("errors", result)
        self.registry.get.assert_not_called()
        self.assertEqual(task.status, "PENDING")
        self.assertEqual(self.state.observations, [])

    def test_empty_required_fields_are_invalid_schema(self):
        tasks = {
            "id": Task("", "CodeAnalysisAgent", "analyze_code", self.state.target),
            "agent": Task("T1", "", "analyze_code", self.state.target),
            "target": Task("T1", "CodeAnalysisAgent", "analyze_code", ""),
        }

        for field, task in tasks.items():
            with self.subTest(field=field):
                result = self.supervisor.delegate(task, self.state)

                self.assertEqual(result["status"], "DENIED")
                self.assertEqual(result["reason"], "INVALID_SCHEMA")
                self.assertEqual(task.status, "PENDING")

    def test_wrong_phase_is_denied_without_running_agent(self):
        agent = Mock()
        self.registry.register(
            "VerificationAgent",
            agent,
            ["verify_sqli"],
        )
        task = Task(
            "T1",
            "VerificationAgent",
            "verify_sqli",
            self.state.target,
        )

        result = self.supervisor.delegate(task, self.state)

        self.assertEqual(
            result,
            {
                "status": "DENIED",
                "reason": "ACTION_NOT_ALLOWED_IN_PHASE",
            },
        )
        agent.run.assert_not_called()
        self.assertEqual(task.status, "PENDING")
        self.assertEqual(self.state.observations, [])

    def test_policy_deny_never_runs_agent(self):
        self.state.phase = "VERIFY"
        agent = Mock()
        self.registry.register(
            "VerificationAgent",
            agent,
            ["execute_command"],
        )
        task = Task(
            "T1",
            "VerificationAgent",
            "execute_command",
            self.state.target,
        )

        result = self.supervisor.delegate(task, self.state)

        self.assertEqual(
            result,
            {"status": "DENIED", "reason": "POLICY_DENIED"},
        )
        agent.run.assert_not_called()
        self.assertEqual(task.status, "PENDING")
        self.assertEqual(self.state.observations, [])

    def test_out_of_scope_never_runs_agent(self):
        agent = Mock()
        self.registry.register(
            "CodeAnalysisAgent",
            agent,
            ["analyze_code"],
        )
        task = Task(
            "T1",
            "CodeAnalysisAgent",
            "analyze_code",
            "./other_app",
        )

        result = self.supervisor.delegate(task, self.state)

        self.assertEqual(
            result,
            {"status": "DENIED", "reason": "TARGET_OUT_OF_SCOPE"},
        )
        agent.run.assert_not_called()
        self.assertEqual(task.status, "PENDING")
        self.assertEqual(self.state.observations, [])

    def test_confirm_waits_without_execution(self):
        self.state.phase = "VERIFY"
        agent = Mock()
        self.registry.register(
            "VerificationAgent",
            agent,
            ["verify_ssrf"],
        )
        task = Task(
            "T1",
            "VerificationAgent",
            "verify_ssrf",
            self.state.target,
        )

        result = self.supervisor.delegate(task, self.state)

        self.assertEqual(
            result,
            {
                "status": "WAITING_CONFIRMATION",
                "reason": "POLICY_CONFIRM",
                "action_id": "A001",
            },
        )
        agent.run.assert_not_called()
        self.assertEqual(task.status, "WAITING_CONFIRMATION")
        self.assertEqual(self.state.observations, [])

    def test_out_of_scope_confirm_action_is_denied_before_confirmation(self):
        self.state.phase = "VERIFY"
        agent = Mock()
        self.registry.register(
            "VerificationAgent",
            agent,
            ["verify_ssrf"],
        )
        task = Task(
            "T1",
            "VerificationAgent",
            "verify_ssrf",
            "./other_app",
        )

        result = self.supervisor.delegate(task, self.state)

        self.assertEqual(
            result,
            {"status": "DENIED", "reason": "TARGET_OUT_OF_SCOPE"},
        )
        agent.run.assert_not_called()
        self.assertEqual(task.status, "PENDING")
        self.assertEqual(self.state.observations, [])


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.state = AgentState("./demo_app")
        self.state.phase = "VERIFY"
        self.registry = AgentRegistry()
        self.agent = Mock()
        self.registry.register(
            "VerificationAgent",
            self.agent,
            ["verify_ssrf"],
        )
        self.supervisor = Supervisor(self.registry)
        self.task = Task(
            "T1",
            "VerificationAgent",
            "verify_ssrf",
            self.state.target,
        )
        self.state.add_task(self.task)

    def test_confirm_creates_pending_action(self):
        result = self.supervisor.delegate(
            self.task,
            self.state,
        )

        self.assertEqual(
            result,
            {
                "status": "WAITING_CONFIRMATION",
                "reason": "POLICY_CONFIRM",
                "action_id": "A001",
            },
        )
        pending = self.supervisor.approval_store.get("A001")
        self.assertEqual(pending.status, "WAITING_CONFIRMATION")
        self.assertEqual(pending.snapshot.id, "T1")
        self.assertEqual(pending.snapshot.agent, "VerificationAgent")
        self.assertEqual(pending.snapshot.action, "verify_ssrf")
        self.assertEqual(pending.snapshot.target, "./demo_app")
        self.assertEqual(self.task.status, "WAITING_CONFIRMATION")
        self.agent.run.assert_not_called()
        self.assertEqual(self.state.observations, [])

    def test_approved_action_executes_once(self):
        observation = {
            "agent": "VerificationAgent",
            "task_id": "T1",
            "execution_status": "SUCCESS",
            "data": {},
        }
        self.agent.run.return_value = observation
        pending_result = self.supervisor.delegate(
            self.task,
            self.state,
        )

        result = self.supervisor.approve(
            pending_result["action_id"],
            self.state,
        )

        self.assertIs(result, observation)
        self.agent.run.assert_called_once()
        executed_request = self.agent.run.call_args.args[0]
        self.assertIsNot(executed_request, self.task)
        self.assertEqual(executed_request.id, "T1")
        self.assertEqual(executed_request.agent, "VerificationAgent")
        self.assertEqual(executed_request.action, "verify_ssrf")
        self.assertEqual(executed_request.target, "./demo_app")
        self.assertEqual(self.task.status, "COMPLETED")
        self.assertEqual(self.state.observations, [observation])
        self.assertEqual(
            self.supervisor.approval_store.get("A001").status,
            "EXECUTED",
        )

    def test_modified_task_is_not_executed(self):
        pending_result = self.supervisor.delegate(
            self.task,
            self.state,
        )
        action_id = pending_result["action_id"]
        self.task.target = "./other_target"

        result = self.supervisor.approve(
            action_id,
            self.state,
        )

        self.assertEqual(
            result,
            {
                "status": "DENIED",
                "reason": "APPROVED_REQUEST_MISMATCH",
            },
        )
        self.agent.run.assert_not_called()
        self.assertEqual(self.task.status, "BLOCKED")
        self.assertEqual(
            self.supervisor.approval_store.get(action_id).status,
            "REJECTED",
        )

    def test_approval_rechecks_capability(self):
        pending_result = self.supervisor.delegate(
            self.task,
            self.state,
        )
        action_id = pending_result["action_id"]
        self.registry.agents[
            "VerificationAgent"
        ]["capabilities"] = []

        result = self.supervisor.approve(
            action_id,
            self.state,
        )

        self.assertEqual(
            result,
            {
                "status": "DENIED",
                "reason": "CAPABILITY_NOT_ALLOWED",
            },
        )
        self.agent.run.assert_not_called()
        self.assertEqual(self.task.status, "BLOCKED")
        self.assertEqual(
            self.supervisor.approval_store.get(action_id).status,
            "REJECTED",
        )

    def test_approval_rechecks_policy(self):
        pending_result = self.supervisor.delegate(
            self.task,
            self.state,
        )
        action_id = pending_result["action_id"]
        self.supervisor.policy.rules[
            "verify_ssrf"
        ] = "DENY"

        result = self.supervisor.approve(
            action_id,
            self.state,
        )

        self.assertEqual(
            result,
            {
                "status": "DENIED",
                "reason": "POLICY_DENIED",
            },
        )
        self.agent.run.assert_not_called()
        self.assertEqual(self.task.status, "BLOCKED")
        self.assertEqual(
            self.supervisor.approval_store.get(action_id).status,
            "REJECTED",
        )

    def test_approval_rechecks_scope(self):
        pending_result = self.supervisor.delegate(
            self.task,
            self.state,
        )
        action_id = pending_result["action_id"]
        self.state.target = "./other_target"

        result = self.supervisor.approve(
            action_id,
            self.state,
        )

        self.assertEqual(
            result,
            {
                "status": "DENIED",
                "reason": "TARGET_OUT_OF_SCOPE",
            },
        )
        self.agent.run.assert_not_called()
        self.assertEqual(self.task.status, "BLOCKED")
        self.assertEqual(
            self.supervisor.approval_store.get(action_id).status,
            "REJECTED",
        )

    def test_approval_cannot_be_replayed(self):
        self.agent.run.return_value = {
            "agent": "VerificationAgent",
            "task_id": "T1",
            "execution_status": "SUCCESS",
            "data": {},
        }
        pending_result = self.supervisor.delegate(
            self.task,
            self.state,
        )
        action_id = pending_result["action_id"]

        first = self.supervisor.approve(
            action_id,
            self.state,
        )
        second = self.supervisor.approve(
            action_id,
            self.state,
        )

        self.assertEqual(first["execution_status"], "SUCCESS")
        self.assertEqual(
            second,
            {
                "status": "DENIED",
                "reason": "INVALID_APPROVAL_STATE",
            },
        )
        self.agent.run.assert_called_once()
        self.assertEqual(len(self.state.observations), 1)

    def test_unknown_action_id_is_denied(self):
        result = self.supervisor.approve(
            "A999",
            self.state,
        )

        self.assertEqual(
            result,
            {
                "status": "DENIED",
                "reason": "UNKNOWN_PENDING_ACTION",
            },
        )
        self.agent.run.assert_not_called()

    def test_unknown_policy_decision_defaults_to_deny(self):
        self.state.phase = "ANALYZE"
        agent = Mock()
        policy = Mock()
        policy.evaluate.return_value = "ALOW"
        supervisor = Supervisor(self.registry, policy=policy)
        self.registry.register(
            "CodeAnalysisAgent",
            agent,
            ["analyze_code"],
        )
        task = Task(
            "T1",
            "CodeAnalysisAgent",
            "analyze_code",
            self.state.target,
        )

        result = supervisor.delegate(task, self.state)

        self.assertEqual(
            result,
            {"status": "DENIED", "reason": "POLICY_DENIED"},
        )
        agent.run.assert_not_called()
        self.assertEqual(task.status, "PENDING")
        self.assertEqual(self.state.observations, [])


class MainTests(unittest.TestCase):
    def test_demo_prints_completed_task_and_observation(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main()

        text = output.getvalue()
        self.assertIn("[CodeAnalysisAgent] analyzing: ./demo_app", text)
        self.assertIn("=== Result ===", text)
        self.assertIn("=== Task Status ===\nCOMPLETED", text)
        self.assertIn("=== Observations ===", text)
        self.assertIn('"potential_findings": [', text)


if __name__ == "__main__":
    unittest.main()
