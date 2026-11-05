import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pydantic import ValidationError

from main import build_runtime, build_tool_executor
from models.approval import ApprovalSnapshot
from models.task import Task
from models.tool import ToolContext
from planner.demo_planner import DemoPlanner
from runtime.policy import PolicyEngine
from runtime.tool_executor import ToolExecutionDenied
from state import AgentState


class RuntimeToolContextTests(unittest.TestCase):
    def setUp(self):
        self.runtime = build_runtime(DemoPlanner())
        self.state = AgentState("./demo_app", authorized_origin="http://127.0.0.1:5000")

    def task(self, action="analyze_code", arguments=None):
        agent = "VerificationAgent" if action == "check_http_baseline" else "CodeAnalysisAgent"
        task = Task("T1", agent, action, self.state.target, arguments=arguments or {}, phase=self.state.phase)
        self.state.tasks.append(task)
        return task

    def test_direct_and_approved_execution_get_trusted_frozen_context(self):
        for require_approval in (False, True):
            with self.subTest(require_approval=require_approval):
                self.setUp()
                task = self.task(arguments={"authorized_root": "E:/", "authorized_origin": "http://other.invalid"})
                agent = Mock()
                agent.run.return_value = {"agent": task.agent, "task_id": task.id,
                                          "execution_status": "SUCCESS", "data": {}}
                self.runtime.registry.agents[task.agent]["instance"] = agent
                if require_approval:
                    self.runtime.supervisor.policy = PolicyEngine({"analyze_code": "CONFIRM"})
                result = self.runtime.supervisor.delegate(task, self.state)
                if require_approval:
                    agent.run.assert_not_called()
                    result = self.runtime.supervisor.approve(result["action_id"], self.state)
                self.assertEqual(result.execution_status, "SUCCESS")
                agent.run.assert_called_once()
                request, context = agent.run.call_args.args
                self.assertIsInstance(request, ApprovalSnapshot)
                self.assertEqual((context.task_id, context.agent, context.action), (task.id, task.agent, task.action))
                self.assertEqual(context.authorized_root, self.state.target)
                self.assertEqual(context.authorized_origin, self.state.authorized_origin)
                with self.assertRaises(ValidationError):
                    context.authorized_root = "E:/"

    def test_legacy_state_without_origin_still_gets_context(self):
        del self.state.authorized_origin
        task = self.task()
        context = self.runtime.supervisor._build_tool_context(ApprovalSnapshot.from_task(task), self.state)
        self.assertIsNone(context.authorized_origin)

    def test_denied_task_never_builds_context_or_calls_agent(self):
        task = self.task()
        task.target = "./unauthorized"
        agent = Mock()
        self.runtime.registry.agents[task.agent]["instance"] = agent
        with patch.object(self.runtime.supervisor, "_build_tool_context") as build:
            result = self.runtime.supervisor.delegate(task, self.state)
            self.assertEqual(result["reason"], "TARGET_OUT_OF_SCOPE")
            build.assert_not_called()
        agent.run.assert_not_called()

    def test_type_error_does_not_retry_agent(self):
        task = self.task()
        agent = Mock()
        agent.run.side_effect = TypeError("internal failure")
        self.runtime.registry.agents[task.agent]["instance"] = agent
        self.assertEqual(self.runtime.supervisor.delegate(task, self.state)["status"], "FAILED")
        agent.run.assert_called_once()

    def test_http_baseline_records_observation_without_evidence_or_findings(self):
        self.state.phase = "VERIFY"
        task = self.task("check_http_baseline")
        with patch("tools.controlled_http.build_opener") as build:
            response = build.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.headers = {"Content-Type": "text/plain"}
            result = self.runtime.supervisor.delegate(task, self.state)
        self.assertEqual(task.status, "COMPLETED")
        self.assertEqual(result.data["http_baseline"]["status_code"], 200)
        self.assertEqual(self.state.observations, [result])
        self.assertEqual(self.state.findings, [])
        self.assertEqual(self.state.evidence, [])

    def test_tool_errors_propagate_to_task_and_observation(self):
        for action, arguments in (("read_file", {"path": "../outside.py"}),
                                  ("analyze_code", {"query": ""}),
                                  ("check_http_baseline", {})):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory:
                self.state = AgentState(directory)
                self.state.phase = "VERIFY" if action == "check_http_baseline" else "ANALYZE"
                task = self.task(action, arguments)
                with patch("tools.controlled_http.build_opener") as build:
                    result = self.runtime.supervisor.delegate(task, self.state)
                    build.assert_not_called()
                self.assertEqual(result.execution_status, "FAILED")
                self.assertEqual(task.status, "FAILED")
                self.assertEqual(self.state.observations, [result])
                self.assertEqual(self.state.evidence, [])

    def test_demo_end_to_end_search_does_not_schedule_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "app.py").write_text("cursor.execute(query)\n", encoding="utf-8")
            state = AgentState(directory, authorized_origin="http://localhost")
            with patch("tools.controlled_http.build_opener") as build:
                result = self.runtime.run_until_blocked("Inspect source", state)
                build.assert_not_called()
        self.assertEqual(result, {"status": "COMPLETED", "failed_task_ids": []})
        self.assertEqual([task.action for task in state.tasks], ["analyze_code", "generate_report"])
        self.assertEqual(state.observations[0].data["matches"][0]["path"], "app.py")
        self.assertEqual(state.findings, [])
        self.assertEqual(state.evidence, [])

    def test_production_allowlist_denies_cross_action_tools(self):
        executor = build_tool_executor()
        for agent, action, tool in (
            ("CodeAnalysisAgent", "analyze_code", "controlled_http_check"),
            ("CodeAnalysisAgent", "read_file", "search_code"),
            ("VerificationAgent", "verify_sqli", "controlled_http_check"),
            ("VerificationAgent", "check_http_baseline", "read_source"),
            ("ReportAgent", "generate_report", "read_source"),
        ):
            context = ToolContext(task_id="T1", agent=agent, action=action)
            with self.subTest(action=action, tool=tool), self.assertRaises(ToolExecutionDenied):
                executor.execute(tool, {}, context)
