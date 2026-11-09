import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import BaseModel, ConfigDict, Field

from models.tool import ToolContext, ToolResult
from runtime.tool_executor import ToolArgumentsInvalid, ToolExecutionDenied, ToolExecutor
from runtime.tool_registry import ToolRegistry


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    max_matches: int = Field(default=30, ge=1, le=80)


class FakeSearchTool:
    name = "search_code"
    args_model = SearchArgs

    def __init__(self):
        self.calls = 0
        self.should_fail = False
        self.received_arguments = None
        self.received_context = None

    def execute(self, args, context):
        self.calls += 1
        self.received_arguments = args
        self.received_context = context
        if self.should_fail:
            raise RuntimeError("private/path.py: sensitive details")
        return {"query": args.query, "max_matches": args.max_matches}


class ToolExecutorTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.tool = FakeSearchTool()
        self.registry.register(self.tool)
        self.allowlist = {("CodeAnalysisAgent", "analyze_code"): {"search_code"}}
        self.executor = ToolExecutor(self.registry, self.allowlist)
        self.context = ToolContext(
            task_id="T1", agent="CodeAnalysisAgent", action="analyze_code",
            authorized_root="./demo_app",
        )

    def test_successful_tool_execution(self):
        result = self.executor.execute("search_code", {"query": "eval("}, self.context)
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.model_dump(), {
            "tool_name": "search_code", "status": "SUCCESS",
            "data": {"query": "eval(", "max_matches": 30}, "error": None,
        })
        self.assertEqual(self.tool.calls, 1)
        self.assertIsInstance(self.tool.received_arguments, SearchArgs)
        self.assertIs(self.tool.received_context, self.context)

    def test_unauthorized_tool_is_denied_before_registry_lookup(self):
        self.registry.get = Mock(wraps=self.registry.get)
        for agent, action in (
            ("ReportAgent", "generate_report"),
            ("CodeAnalysisAgent", "read_file"),
            ("VerificationAgent", "verify_sqli"),
            ("VerificationAgent", "verify_ssrf"),
        ):
            with self.subTest(agent=agent, action=action):
                context = ToolContext(task_id="T1", agent=agent, action=action)
                with self.assertRaisesRegex(ToolExecutionDenied, "^TOOL_NOT_ALLOWED_FOR_ACTION$"):
                    self.executor.execute("search_code", {"query": "eval("}, context)
        self.registry.get.assert_not_called()
        self.assertEqual(self.tool.calls, 0)

    def test_invalid_arguments_do_not_execute_tool(self):
        for arguments in (
            {}, {"query": ""}, {"query": "eval(", "max_matches": 999},
            {"query": "eval(", "unexpected": True}, None, [], "eval(",
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(ToolArgumentsInvalid, "^INVALID_TOOL_ARGUMENTS$"):
                    self.executor.execute("search_code", arguments, self.context)
        self.assertEqual(self.tool.calls, 0)

    def test_model_instance_cannot_bypass_argument_validation(self):
        arguments = SearchArgs.model_construct(query="", max_matches=999)
        with self.assertRaisesRegex(ToolArgumentsInvalid, "^INVALID_TOOL_ARGUMENTS$"):
            self.executor.execute("search_code", arguments, self.context)
        self.assertEqual(self.tool.calls, 0)

    def test_unknown_registered_tool_is_denied(self):
        executor = ToolExecutor(self.registry, {
            ("CodeAnalysisAgent", "analyze_code"): {"missing_tool"},
        })
        with self.assertRaisesRegex(ToolExecutionDenied, "^UNKNOWN_TOOL$"):
            executor.execute("missing_tool", {"query": "eval("}, self.context)
        self.assertEqual(self.tool.calls, 0)

    def test_tool_exception_returns_error_result(self):
        self.tool.should_fail = True
        result = self.executor.execute("search_code", {"query": "eval("}, self.context)
        self.assertEqual(result.model_dump(), {
            "tool_name": "search_code", "status": "ERROR",
            "data": {}, "error": "RuntimeError",
        })
        self.assertNotIn("sensitive", result.model_dump_json())
        self.assertEqual(self.tool.calls, 1)

    def test_invalid_tool_result_returns_error(self):
        for raw_data in (None, [], "private/path.py", {1: "sensitive details"}):
            with self.subTest(raw_data=raw_data):
                execute = Mock(return_value=raw_data)
                self.tool.execute = execute
                result = self.executor.execute("search_code", {"query": "eval("}, self.context)
                self.assertEqual(result.model_dump(), {
                    "tool_name": "search_code", "status": "ERROR",
                    "data": {}, "error": "INVALID_TOOL_RESULT",
                })
                execute.assert_called_once()

    def test_allowlist_is_copied(self):
        mutable_tools = self.allowlist[("CodeAnalysisAgent", "analyze_code")]
        mutable_tools.clear()
        mutable_tools.add("missing_tool")
        self.allowlist.clear()
        result = self.executor.execute("search_code", {"query": "eval("}, self.context)
        self.assertEqual(result.status, "SUCCESS")
        with self.assertRaisesRegex(ToolExecutionDenied, "^TOOL_NOT_ALLOWED_FOR_ACTION$"):
            self.executor.execute("missing_tool", {}, self.context)
        self.assertEqual(self.tool.calls, 1)

    def test_invalid_context_does_not_execute_tool(self):
        for context in (None, self.context.model_dump(), SimpleNamespace(**self.context.model_dump())):
            with self.subTest(context=context):
                with self.assertRaisesRegex(TypeError, "^INVALID_TOOL_CONTEXT$"):
                    self.executor.execute("search_code", {"query": "eval("}, context)
        self.assertEqual(self.tool.calls, 0)

    def test_invalid_tool_name_does_not_execute_tool(self):
        for name in (None, "", [], 123):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ToolExecutionDenied, "^UNKNOWN_TOOL$"):
                    self.executor.execute(name, {"query": "eval("}, self.context)
        self.assertEqual(self.tool.calls, 0)

    def test_invalid_allowlist_configuration_is_rejected(self):
        cases = (
            ({"CodeAnalysisAgent": {"search_code"}}, "INVALID_ALLOWLIST_KEY"),
            ({("CodeAnalysisAgent",): set()}, "INVALID_ALLOWLIST_KEY"),
            ({("", "analyze_code"): set()}, "INVALID_AGENT_NAME"),
            ({(123, "analyze_code"): set()}, "INVALID_AGENT_NAME"),
            ({("CodeAnalysisAgent", ""): set()}, "INVALID_ACTION_NAME"),
            ({("CodeAnalysisAgent", 123): set()}, "INVALID_ACTION_NAME"),
        )
        for allowlist, reason in cases:
            with self.subTest(allowlist=allowlist):
                with self.assertRaisesRegex(ValueError, f"^{reason}$"):
                    ToolExecutor(self.registry, allowlist)

    def test_invalid_tool_allowlist_is_rejected(self):
        for names in ("search_code", b"search_code", None, 123, [["search_code"]]):
            with self.subTest(names=names):
                with self.assertRaisesRegex(ValueError, "^INVALID_TOOL_ALLOWLIST$"):
                    ToolExecutor(self.registry, {("CodeAnalysisAgent", "analyze_code"): names})

    def test_invalid_allowlist_tool_name_is_rejected(self):
        for name in (None, "", 123, "search-code"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "^INVALID_TOOL_NAME$"):
                    ToolExecutor(self.registry, {("CodeAnalysisAgent", "analyze_code"): [name]})


if __name__ == "__main__":
    unittest.main()
