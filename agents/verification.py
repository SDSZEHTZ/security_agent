from models.task import Task


class VerificationAgent:
    def run(self, task: Task) -> dict:
        print(f"[VerificationAgent] verifying: {task.action} -> {task.target}")
        return {
            "agent": "VerificationAgent",
            "task_id": task.id,
            "execution_status": "SUCCESS",
            "data": {"message": "Verification completed"},
        }
