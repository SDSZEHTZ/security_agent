import unittest

from pydantic import ValidationError

from models.task import Task
from models.tool import ToolContext, ToolResult
from runtime.validator import RequestValidator


class ToolModelTests(unittest.TestCase):
    def test_task_arguments_are_independent(self):
        first = Task("T1", "CodeAnalysisAgent", "analyze_code", "./demo_app")
        second = Task("T2", "CodeAnalysisAgent", "analyze_code", "./demo_app")
        first.arguments["query"] = "eval("
        self.assertEqual(first.arguments, {"query": "eval("})
        self.assertEqual(second.arguments, {})

    def test_request_validator_preserves_arguments(self):
        task = Task(
            "T1", "CodeAnalysisAgent", "analyze_code", "./demo_app",
            arguments={"query": "eval(", "max_matches": 30, "enabled": True},
        )
        request = RequestValidator().validate(task)
        self.assertEqual(request.arguments, task.arguments)

    def test_tool_results_have_independent_data_and_accept_mixed_values(self):
        first = ToolResult(tool_name="read_file", status="SUCCESS")
        second = ToolResult(tool_name="read_file", status="SUCCESS")
        first.data.update({"path": "src/app.py", "count": 2, "truncated": False})
        self.assertEqual(first.data, {"path": "src/app.py", "count": 2, "truncated": False})
        self.assertEqual(second.data, {})
        failure = ToolResult(tool_name="read_file", status="ERROR", error="File not found")
        self.assertEqual(failure.error, "File not found")

    def test_tool_result_rejects_invalid_fields(self):
        valid = {"tool_name": "read_file", "status": "SUCCESS"}
        for update in ({"tool_name": ""}, {"status": "PENDING"}, {"unknown": True}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ToolResult(**{**valid, **update})

    def test_tool_context_rejects_invalid_fields(self):
        valid = {"task_id": "T1", "agent": "CodeAnalysisAgent", "action": "read_file"}
        for update in (
            {"task_id": ""}, {"agent": ""}, {"action": "invented_action"}, {"unknown": True},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ToolContext(**{**valid, **update})

    def test_tool_context_is_frozen(self):
        context = ToolContext(
            task_id="T1", agent="CodeAnalysisAgent", action="read_file",
            authorized_root="./demo_app", authorized_origin="https://example.com",
        )
        for field, value in (
            ("task_id", "T2"), ("authorized_root", "./other_app"),
            ("authorized_origin", "https://other.example.com"),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                setattr(context, field, value)
        self.assertEqual(context.authorized_root, "./demo_app")
        self.assertEqual(context.authorized_origin, "https://example.com")


if __name__ == "__main__":
    unittest.main()
