from models.approval import ApprovalSnapshot
from models.tool import ToolContext
from runtime.tool_executor import ToolArgumentsInvalid, ToolExecutionDenied, ToolExecutor


class VerificationAgent:
    def __init__(self, tool_executor: ToolExecutor):
        self.tool_executor = tool_executor

    def run(self, task: ApprovalSnapshot, tool_context: ToolContext) -> dict:
        if task.action == "check_http_baseline":
            return self._check_http(task, tool_context)

        # These are deterministic teaching fixtures, NOT vulnerability checks.
        # No network/tool request is performed for either action.
        print(f"[VerificationAgent] DEMO fixture: {task.action} -> {task.target}")

        if task.action == "verify_sqli":
            data = {
                "status_code": 500,
                "response": "Database error: SQL syntax error",
            }
        elif task.action == "verify_ssrf":
            data = {
                "request_completed": True,
                "callback_received": False,
            }
        else:
            return self._observation(task, "FAILED", {"reason": "UNSUPPORTED_ACTION"})

        # This explicit marker is a defense against accidental evidence promotion,
        # not authentication: untrusted third-party Agents require a separate trust boundary.
        return self._observation(task, "SUCCESS", {
            **data,
            "verification_mode": "DEMO_FIXTURE",
        })

    def _check_http(self, task, tool_context):
        arguments = task.arguments
        tool_name = "controlled_http_check"
        try:
            result = self.tool_executor.execute(tool_name, {
                "path": arguments.get("path", "/"),
                "method": arguments.get("method", "HEAD"),
            }, tool_context)
        except (ToolArgumentsInvalid, ToolExecutionDenied) as exc:
            return self._observation(task, "FAILED", {
                "tool_name": tool_name, "reason": str(exc),
            })
        if result.status != "SUCCESS":
            return self._observation(task, "FAILED", {
                "tool_name": tool_name, "reason": "TOOL_EXECUTION_FAILED",
                "error": result.error,
            })
        # Keep HTTP baseline data separate from verified vulnerability evidence.
        # A successful baseline describes reachability/response metadata only.
        return self._observation(task, "SUCCESS", {
            "tool_name": tool_name,
            "http_baseline": result.data,
        })

    @staticmethod
    def _observation(task, status, data):
        return {
            "agent": "VerificationAgent",
            "task_id": task.id,
            "execution_status": status,
            "data": data,
        }
