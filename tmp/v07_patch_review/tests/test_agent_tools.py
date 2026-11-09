import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.code_analysis import CodeAnalysisAgent
from agents.verification import VerificationAgent
from main import build_tool_executor
from models.approval import ApprovalSnapshot
from models.task import Task
from models.tool import ToolContext
from runtime.tool_executor import ToolExecutor
from runtime.tool_registry import ToolRegistry


class AgentToolTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "app.py").write_bytes(b"cursor.execute(query)\n")
        self.executor = build_tool_executor()

    def run_agent(self, action, arguments=None, origin=None, executor=None):
        agent_type = VerificationAgent if action == "check_http_baseline" else CodeAnalysisAgent
        task = Task("T1", agent_type.__name__, action, str(self.root), arguments=arguments or {})
        context = ToolContext(task_id=task.id, agent=task.agent, action=action,
                              authorized_root=str(self.root), authorized_origin=origin)
        return agent_type(executor or self.executor).run(ApprovalSnapshot.from_task(task), context)

    def test_search_reads_real_source_without_creating_findings(self):
        result = self.run_agent("analyze_code", {"query": "execute(", "max_matches": 1})
        self.assertEqual(result["execution_status"], "SUCCESS")
        self.assertEqual(result["data"]["matches"], [
            {"path": "app.py", "line": 1, "snippet": "cursor.execute(query)"},
        ])
        self.assertNotIn("potential_findings", result["data"])
        self.assertEqual(self.run_agent("analyze_code", {"query": "absent"})["data"]["matches"], [])

    def test_read_returns_real_source(self):
        result = self.run_agent("read_file", {"path": "app.py"})
        self.assertEqual(result["execution_status"], "SUCCESS")
        self.assertEqual(result["data"]["content"], "cursor.execute(query)\n")

    def test_required_and_invalid_arguments_fail(self):
        for action, arguments, reason in (
            ("analyze_code", {}, "SEARCH_QUERY_REQUIRED"),
            ("read_file", {}, "SOURCE_PATH_REQUIRED"),
            ("analyze_code", {"query": " "}, "INVALID_TOOL_ARGUMENTS"),
            ("analyze_code", {"query": "execute(", "max_matches": 0}, "INVALID_TOOL_ARGUMENTS"),
            ("read_file", {"path": ""}, "INVALID_TOOL_ARGUMENTS"),
        ):
            with self.subTest(action=action, arguments=arguments):
                result = self.run_agent(action, arguments)
                self.assertEqual(result["execution_status"], "FAILED")
                self.assertEqual(result["data"]["reason"], reason)

    def test_outside_root_cannot_be_read(self):
        with tempfile.TemporaryDirectory() as outside:
            secret = Path(outside, "outside.py")
            secret.write_text("outside secret", encoding="utf-8")
            for path in (str(secret), "../outside.py"):
                result = self.run_agent("read_file", {"path": path, "authorized_root": outside})
                self.assertEqual(result["execution_status"], "FAILED")
                self.assertNotIn("outside secret", str(result))

    def test_denied_tool_becomes_failed_observation(self):
        denied = ToolExecutor(ToolRegistry(), {})
        for action, arguments in (("analyze_code", {"query": "execute("}),
                                  ("check_http_baseline", {})):
            result = self.run_agent(action, arguments, executor=denied)
            self.assertEqual(result["execution_status"], "FAILED")
            self.assertEqual(result["data"]["reason"], "TOOL_NOT_ALLOWED_FOR_ACTION")

    def test_http_defaults_and_explicit_get_use_runtime_origin(self):
        with patch("tools.controlled_http.build_opener") as build_opener:
            response = build_opener.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.headers = {"Content-Type": "text/plain"}
            response.read.return_value = b"ok"
            for arguments, method, path in (({}, "HEAD", "/"),
                                             ({"method": "GET", "path": "/health"}, "GET", "/health")):
                with self.subTest(method=method):
                    result = self.run_agent("check_http_baseline", {
                        **arguments, "origin": "http://untrusted.invalid",
                        "authorized_origin": "http://untrusted.invalid",
                    }, origin="http://127.0.0.1:5000")
                    self.assertEqual(result["execution_status"], "SUCCESS")
                    request = build_opener.return_value.open.call_args.args[0]
                    self.assertEqual(request.full_url, "http://127.0.0.1:5000" + path)
                    self.assertEqual(request.get_method(), method)
                    self.assertEqual(result["data"]["http_baseline"]["status_code"], 200)
                    self.assertNotIn("potential_findings", result["data"])

    def test_http_missing_origin_and_invalid_arguments_never_open_connection(self):
        with patch("tools.controlled_http.build_opener") as build_opener:
            cases = [({}, None), ({}, "not-an-origin"), ({"method": "POST"}, "http://localhost"),
                     ({"path": "https://other.invalid/"}, "http://localhost"),
                     ({"path": "//other.invalid/"}, "http://localhost")]
            for arguments, origin in cases:
                with self.subTest(arguments=arguments, origin=origin):
                    result = self.run_agent("check_http_baseline", arguments, origin=origin)
                    self.assertEqual(result["execution_status"], "FAILED")
            build_opener.assert_not_called()

    def test_http_timeout_is_failed_and_does_not_leak_exception_message(self):
        with patch("tools.controlled_http.build_opener") as build_opener:
            build_opener.return_value.open.side_effect = TimeoutError("private details")
            result = self.run_agent("check_http_baseline", origin="http://localhost")
        self.assertEqual(result["execution_status"], "FAILED")
        self.assertEqual(result["data"]["error"], "TimeoutError")
        self.assertNotIn("private details", str(result))

    def test_unsupported_actions_do_not_call_tools(self):
        executor = Mock()
        task = ApprovalSnapshot.from_task(Task("T1", "ReportAgent", "generate_report", str(self.root)))
        context = ToolContext(task_id=task.id, agent=task.agent, action=task.action)
        for agent in (CodeAnalysisAgent(executor), VerificationAgent(executor)):
            result = agent.run(task, context)
            self.assertEqual(result["data"]["reason"], "UNSUPPORTED_ACTION")
        executor.execute.assert_not_called()
