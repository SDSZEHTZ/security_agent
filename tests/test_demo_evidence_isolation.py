import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from agents.verification import VerificationAgent
from main import build_registry, build_tool_executor
from models.finding import Finding
from models.observation import Observation
from models.task import Task
from runtime.evidence import EvidenceExtractor
from runtime.planning_context import PlanningContextBuilder
from runtime.supervisor import Supervisor
from state import AgentState


class DemoEvidenceIsolationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def _run_demo(self, action, finding_type):
        executor = Mock()
        registry = build_registry(build_tool_executor())
        registry.agents["VerificationAgent"]["instance"] = VerificationAgent(executor)
        supervisor = Supervisor(registry)
        state = AgentState(str(self.root))
        state.phase = "VERIFY"
        finding = Finding(id="F1", finding_type=finding_type, target=state.target)
        task = Task("T1", "VerificationAgent", action, state.target, finding_id="F1", phase="VERIFY")
        state.findings.append(finding)
        state.tasks.append(task)
        if action == "verify_ssrf":
            pending = supervisor.delegate(task, state)
            self.assertEqual(pending["status"], "WAITING_CONFIRMATION")
            result = supervisor.approve(pending["action_id"], state)
        else:
            result = supervisor.delegate(task, state)
        self.assertEqual(result.execution_status, "SUCCESS")
        self.assertEqual(result.data["verification_mode"], "DEMO_FIXTURE")
        self.assertEqual(task.status, "COMPLETED")
        self.assertEqual(state.evidence, [])
        self.assertNotEqual(finding.status, "CONFIRMED")
        self.assertEqual(finding.status, "UNCONFIRMED")
        executor.execute.assert_not_called()
        context = PlanningContextBuilder().build(state, registry)
        self.assertEqual(context["recent_observations"], [{
            "task_id": task.id,
            "execution_status": "SUCCESS",
            "data": {"verification_mode": "DEMO_FIXTURE"},
        }])
        return result

    def test_demo_sqli_does_not_promote_finding(self):
        self._run_demo("verify_sqli", "SQL Injection")

    def test_demo_ssrf_does_not_promote_finding(self):
        self._run_demo("verify_ssrf", "SSRF")

    def test_extractor_ignores_fixture_even_if_strong_signal_present(self):
        observation = Observation(
            agent="VerificationAgent", task_id="T1", execution_status="SUCCESS",
            data={"verification_mode": "DEMO_FIXTURE",
                  "boolean_difference": True, "callback_received": True,
                  "response": "SQL syntax"},
        )
        extractor = EvidenceExtractor()
        for action in ("verify_sqli", "verify_ssrf"):
            with self.subTest(action=action):
                task = Task("T1", "VerificationAgent", action, str(self.root), finding_id="F1")
                self.assertEqual(extractor.extract(observation, task), [])
        self.assertEqual(extractor._next_id, 1)

    def test_http_baseline_remains_not_evidence(self):
        observation = Observation(
            agent="VerificationAgent", task_id="T1", execution_status="SUCCESS",
            data={"http_baseline": {"status_code": 500}},
        )
        task = Task("T1", "VerificationAgent", "check_http_baseline", str(self.root), finding_id="F1")
        self.assertEqual(EvidenceExtractor().extract(observation, task), [])

    def test_planner_omits_all_fixture_signals_and_preserves_real_observations(self):
        fixture_data = {
            "verification_mode": "DEMO_FIXTURE", "status_code": 500,
            "boolean_difference": True, "callback_received": True,
            "request_completed": True, "potential_findings": ["SQL Injection"],
            "response": "SQL syntax",
        }
        state = AgentState(str(self.root))
        state.observations = [
            Observation(agent="VerificationAgent", task_id="T1",
                        execution_status="SUCCESS", data=fixture_data.copy()),
            Observation(agent="VerificationAgent", task_id="T2",
                        execution_status="SUCCESS", data={"status_code": 200}),
        ]
        registry = build_registry(build_tool_executor())
        context = PlanningContextBuilder().build(state, registry)
        self.assertEqual(context["recent_observations"][0]["data"],
                         {"verification_mode": "DEMO_FIXTURE"})
        self.assertEqual(context["recent_observations"][1]["data"], {"status_code": 200})
        self.assertEqual(state.observations[0].data, fixture_data)


if __name__ == "__main__":
    unittest.main()
