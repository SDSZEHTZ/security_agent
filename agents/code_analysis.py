from models.task import Task


class CodeAnalysisAgent:
    def run(self, task: Task) -> dict:
        print(f"[CodeAnalysisAgent] analyzing: {task.target}")
        return {
            "agent": "CodeAnalysisAgent",
            "task_id": task.id,
            "execution_status": "SUCCESS",
            "data": {
                "message": "Code analysis completed",
                "potential_findings": ["SQL Injection"],
            },
        }
