class ReportAgent:
    """Mock report task; the CLI renders authoritative runtime state separately."""

    def run(self, task, tool_context=None):
        return {
            "agent": "ReportAgent",
            "task_id": task.id,
            "execution_status": "SUCCESS",
            "data": {
                "message": "Mock report task completed. See runtime findings and evidence.",
                "demo_only": True,
            },
        }
