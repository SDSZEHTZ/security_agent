from models.approval import ApprovalSnapshot
from models.tool import ToolContext
from runtime.tool_executor import ToolArgumentsInvalid, ToolExecutionDenied, ToolExecutor


class CodeAnalysisAgent:
    def __init__(self, tool_executor: ToolExecutor):
        self.tool_executor = tool_executor

    def run(self, task: ApprovalSnapshot, tool_context: ToolContext) -> dict:
        if task.action == "analyze_code":
            return self._analyze_code(task, tool_context)
        if task.action == "read_file":
            return self._read_file(task, tool_context)
        return self._observation(task, "FAILED", {"reason": "UNSUPPORTED_ACTION"})

    def _analyze_code(self, task, tool_context):
        arguments = task.arguments
        query = arguments.get("query")
        if not isinstance(query, str):
            return self._observation(task, "FAILED", {"reason": "SEARCH_QUERY_REQUIRED"})
        return self._execute_tool(task, tool_context, "search_code", {
            "query": query,
            "max_matches": arguments.get("max_matches", 20),
        })

    def _read_file(self, task, tool_context):
        path = task.arguments.get("path")
        if not isinstance(path, str):
            return self._observation(task, "FAILED", {"reason": "SOURCE_PATH_REQUIRED"})
        return self._execute_tool(task, tool_context, "read_source", {"path": path})

    def _execute_tool(self, task, tool_context, tool_name, arguments):
        try:
            result = self.tool_executor.execute(tool_name, arguments, tool_context)
        except (ToolArgumentsInvalid, ToolExecutionDenied) as exc:
            return self._observation(task, "FAILED", {
                "tool_name": tool_name, "reason": str(exc),
            })
        if result.status != "SUCCESS":
            return self._observation(task, "FAILED", {
                "tool_name": tool_name, "reason": "TOOL_EXECUTION_FAILED",
                "error": result.error,
            })
        # Search hits and source contents are observations, not vulnerability findings.
        return self._observation(task, "SUCCESS", {
            "tool_name": tool_name, **result.data,
        })

    @staticmethod
    def _observation(task, status, data):
        return {
            "agent": "CodeAnalysisAgent",
            "task_id": task.id,
            "execution_status": status,
            "data": data,
        }
