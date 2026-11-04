from models.approval import ApprovalSnapshot


class VerificationAgent:
    def run(self, task: ApprovalSnapshot) -> dict:
        print(f"[VerificationAgent] verifying: {task.action} -> {task.target}")

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
            data = {}

        return {
            "agent": "VerificationAgent",
            "task_id": task.id,
            "execution_status": "SUCCESS",
            "data": data,
        }
