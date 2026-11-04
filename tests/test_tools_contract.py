import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from models.tool import ToolContext, ToolResult
from runtime.tool_executor import ToolExecutionDenied, ToolExecutor
from runtime.tool_registry import ToolRegistry
from tools.controlled_http import ControlledHttpCheckTool
from tools.read_source import ReadSourceTool
from tools.search_code import SearchCodeTool


class RealToolContractTests(unittest.TestCase):
    def registry(self):
        registry = ToolRegistry()
        for tool in (ReadSourceTool(), SearchCodeTool(), ControlledHttpCheckTool()):
            registry.register(tool)
        return registry

    def test_all_tools_satisfy_registry_contract(self):
        registry = self.registry()
        self.assertEqual(registry.names(), ("read_source", "search_code", "controlled_http_check"))

    def test_real_file_tools_execute_through_executor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            (Path(temp_dir) / "app.py").write_bytes(b"eval(user_input)\n")
            context = ToolContext(
                task_id="T1", agent="CodeAnalysisAgent", action="analyze_code",
                authorized_root=temp_dir,
            )
            executor = ToolExecutor(self.registry(), {
                ("CodeAnalysisAgent", "analyze_code"): {"read_source", "search_code"},
            })
            read = executor.execute("read_source", {"path": "app.py"}, context)
            search = executor.execute("search_code", {"query": "eval("}, context)
            self.assertIsInstance(read, ToolResult)
            self.assertEqual(read.status, "SUCCESS")
            self.assertEqual(read.data["content"], "eval(user_input)\n")
            self.assertEqual(search.status, "SUCCESS")
            self.assertEqual(search.data["matches"][0]["path"], "app.py")

    def test_registered_http_tool_stays_denied_without_explicit_permission(self):
        executor = ToolExecutor(self.registry(), {
            ("CodeAnalysisAgent", "analyze_code"): {"read_source", "search_code"},
        })
        context = ToolContext(task_id="T1", agent="CodeAnalysisAgent", action="analyze_code")
        with patch("tools.controlled_http.build_opener") as opener:
            with self.assertRaises(ToolExecutionDenied):
                executor.execute("controlled_http_check", {}, context)
            opener.assert_not_called()

    def test_http_timeout_is_wrapped_without_sensitive_exception_details(self):
        executor = ToolExecutor(self.registry(), {
            ("CodeAnalysisAgent", "analyze_code"): {"controlled_http_check"},
        })
        context = ToolContext(
            task_id="T1", agent="CodeAnalysisAgent", action="analyze_code",
            authorized_origin="https://example.com",
        )
        opener = Mock()
        opener.open.side_effect = TimeoutError("sensitive details")
        with patch("tools.controlled_http.build_opener", return_value=opener):
            result = executor.execute("controlled_http_check", {}, context)
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.error, "TimeoutError")
        self.assertNotIn("sensitive", result.model_dump_json())


if __name__ == "__main__":
    unittest.main()
