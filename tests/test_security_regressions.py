import unittest
from unittest.mock import Mock

from main import build_runtime
from models.finding import Finding
from models.task import Task
from planner.demo_planner import DemoPlanner
from state import AgentState


class SecurityRegressionTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(DemoPlanner())
        self.supervisor = self.runtime.supervisor
        self.state = AgentState("./demo_app")
        self.state.phase = "VERIFY"
        self.agent = Mock()
        self.agent.run.side_effect = lambda task: {
            "agent": task.agent, "task_id": task.id,
            "execution_status": "SUCCESS", "data": {"boolean_difference": True},
        }
        self.runtime.registry.agents["VerificationAgent"]["instance"] = self.agent
        self.task = Task("T1", "VerificationAgent", "verify_ssrf", self.state.target, phase="VERIFY")
        self.state.tasks.append(self.task)

    def test_repeated_dispatch_cannot_create_multiple_approvals(self):
        first = self.supervisor.delegate(self.task, self.state)
        second = self.supervisor.delegate(self.task, self.state)
        self.assertEqual(second["reason"], "INVALID_TASK_STATE")
        self.assertEqual(len(self.supervisor.approval_store.actions), 1)
        self.assertEqual(self.task.status, "WAITING_CONFIRMATION")
        self.supervisor.approve(first["action_id"], self.state)
        self.assertEqual(self.supervisor.delegate(self.task, self.state)["reason"], "INVALID_TASK_STATE")
        self.assertEqual(self.task.status, "COMPLETED")
        self.agent.run.assert_called_once()

    def test_approval_snapshot_freezes_arguments_and_rejects_mutation(self):
        for mutation in ("path", "nested"):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.task.arguments = {"path": "src/app.py", "options": {"max_depth": 2}}
                pending = self.supervisor.delegate(self.task, self.state)
                action = self.supervisor.approval_store.get(pending["action_id"])
                snapshot = action.snapshot
                self.assertEqual(snapshot.arguments, self.task.arguments)

                exposed_arguments = snapshot.arguments
                exposed_arguments["path"] = "tampered.py"
                exposed_arguments["options"]["max_depth"] = 99
                self.assertEqual(snapshot.arguments, {
                    "path": "src/app.py", "options": {"max_depth": 2},
                })

                if mutation == "path":
                    self.task.arguments["path"] = "other.py"
                else:
                    self.task.arguments["options"]["max_depth"] = 3
                self.assertEqual(snapshot.arguments, {
                    "path": "src/app.py", "options": {"max_depth": 2},
                })
                result = self.supervisor.approve(pending["action_id"], self.state)
                self.assertEqual(result, {
                    "status": "DENIED", "reason": "APPROVED_REQUEST_MISMATCH",
                })
                self.assertEqual(action.status, "REJECTED")
                self.agent.run.assert_not_called()

    def test_direct_execution_preserves_arguments_and_isolates_agent_mutation(self):
        self.task.action = "verify_sqli"
        self.task.arguments = {"path": "src/app.py", "options": {"max_depth": 2}}

        def run(request):
            self.assertEqual(request.arguments, self.task.arguments)
            exposed_arguments = request.arguments
            exposed_arguments["options"]["max_depth"] = 99
            self.assertEqual(request.arguments["options"]["max_depth"], 2)
            return {
                "agent": request.agent, "task_id": request.id,
                "execution_status": "SUCCESS", "data": {},
            }

        self.agent.run.side_effect = run
        result = self.supervisor.delegate(self.task, self.state)
        self.assertEqual(result.execution_status, "SUCCESS")
        self.assertEqual(self.task.arguments["options"]["max_depth"], 2)
        self.assertEqual(self.task.status, "COMPLETED")
        self.agent.run.assert_called_once()

    def test_approval_is_bound_to_original_state(self):
        pending = self.supervisor.delegate(self.task, self.state)
        other = AgentState(self.state.target)
        other.phase = "VERIFY"
        other.tasks.append(Task("T1", "VerificationAgent", "verify_ssrf", other.target,
                                phase="VERIFY", status="WAITING_CONFIRMATION"))
        result = self.supervisor.approve(pending["action_id"], other)
        self.assertEqual(result["reason"], "APPROVAL_STATE_MISMATCH")
        self.agent.run.assert_not_called()
        self.supervisor.approve(pending["action_id"], self.state)
        self.agent.run.assert_called_once()

    def test_approval_rechecks_task_phase_dependencies_and_status(self):
        for mutation in ("phase", "dependencies", "status"):
            with self.subTest(mutation=mutation):
                self.setUp()
                pending = self.supervisor.delegate(self.task, self.state)
                if mutation == "phase":
                    self.task.phase = "ANALYZE"
                elif mutation == "dependencies":
                    self.task.dependencies = ["T9"]
                else:
                    self.task.status = "BLOCKED"
                result = self.supervisor.approve(pending["action_id"], self.state)
                self.assertEqual(result["status"], "DENIED")
                self.agent.run.assert_not_called()

    def test_approval_rechecks_dependency_completion(self):
        dependency = Task("T0", "VerificationAgent", "verify_sqli", self.state.target,
                          phase="VERIFY", status="COMPLETED")
        self.state.tasks.append(dependency)
        self.task.dependencies.append(dependency.id)
        pending = self.supervisor.delegate(self.task, self.state)
        dependency.status = "FAILED"
        result = self.supervisor.approve(pending["action_id"], self.state)
        self.assertEqual(result["reason"], "DEPENDENCY_NOT_COMPLETED")
        self.agent.run.assert_not_called()

    def test_cross_target_or_cross_type_finding_cannot_be_confirmed(self):
        for finding_type, target, reason in (
            ("SQL Injection", "./other", "FINDING_TARGET_MISMATCH"),
            ("SSRF", self.state.target, "FINDING_TYPE_MISMATCH"),
        ):
            with self.subTest(reason=reason):
                self.task.status = "PENDING"
                self.task.action = "verify_sqli"
                self.task.finding_id = "F1"
                self.state.findings = [Finding(id="F1", finding_type=finding_type, target=target)]
                result = self.supervisor.delegate(self.task, self.state)
                self.assertEqual(result["reason"], reason)
                self.assertEqual(self.state.findings[0].status, "POTENTIAL")
                self.assertEqual(self.state.evidence, [])
                self.agent.run.assert_not_called()

    def test_terminal_finding_does_not_crash_evaluator(self):
        self.task.action = "verify_sqli"
        self.task.finding_id = "F1"
        self.state.findings = [Finding(id="F1", finding_type="SQL Injection",
                                       target=self.state.target, status="REJECTED")]
        result = self.supervisor.delegate(self.task, self.state)
        self.assertEqual(result["reason"], "FINDING_ALREADY_TERMINAL")
        self.agent.run.assert_not_called()

    def test_future_read_file_task_cannot_bypass_scheduler(self):
        self.state.phase = "ANALYZE"
        self.task.agent = "CodeAnalysisAgent"
        self.task.action = "read_file"
        self.assertEqual(self.supervisor.delegate(self.task, self.state)["reason"], "TASK_PHASE_MISMATCH")

    def test_dependency_and_ownership_are_checked_on_direct_dispatch(self):
        self.task.action = "verify_sqli"
        self.task.dependencies = ["missing"]
        self.assertEqual(self.supervisor.delegate(self.task, self.state)["reason"], "DEPENDENCY_NOT_COMPLETED")
        self.task.status = "PENDING"
        self.task.dependencies = []
        self.state.tasks = []
        self.assertEqual(self.supervisor.delegate(self.task, self.state)["reason"], "TASK_NOT_OWNED_BY_RUNTIME")
        self.agent.run.assert_not_called()

    def test_agent_receives_frozen_request_not_runtime_task(self):
        self.task.action = "verify_sqli"
        def mutate(request):
            request.target = "./other"
        self.agent.run.side_effect = mutate
        result = self.supervisor.delegate(self.task, self.state)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(self.task.target, self.state.target)
        self.assertEqual(self.state.observations, [])

    def test_findings_are_runtime_owned_and_deduplicated(self):
        self.state.phase = "ANALYZE"
        self.task.phase = "ANALYZE"
        self.task.agent = "CodeAnalysisAgent"
        self.task.action = "analyze_code"
        self.runtime.registry.agents["CodeAnalysisAgent"]["instance"] = self.agent
        self.agent.run.side_effect = lambda task: {
            "agent": task.agent, "task_id": task.id, "execution_status": "SUCCESS",
            "data": {"potential_findings": [
                "SQL Injection", "SQL Injection", {"id": "F9", "status": "CONFIRMED"}, "SSRF",
            ]},
        }
        self.supervisor.delegate(self.task, self.state)
        self.assertEqual([finding.id for finding in self.state.findings], ["F1", "F2"])
        self.assertTrue(all(finding.status == "POTENTIAL" and finding.target == self.state.target
                            for finding in self.state.findings))


if __name__ == "__main__":
    unittest.main()
