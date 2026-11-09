from runtime.workflow import WorkflowEngine


class PlanningContextBuilder:
    MAX_OBSERVATIONS = 5
    MAX_TEXT_LENGTH = 1000
    MAX_FINDINGS = 50
    MAX_COMPLETED_TASKS = 30
    SIGNAL_KEYS = ("boolean_difference", "callback_received", "request_completed")

    def build(self, state, registry):
        findings = self._findings(state)
        return {
            "authorized_target": state.target,
            "allowed_actions": sorted(WorkflowEngine.ALLOWED_ACTIONS.get(state.phase, set())),
            "available_agents": {
                name: {"capabilities": list(info["capabilities"])}
                for name, info in registry.agents.items()
            },
            "findings": findings,
            "findings_omitted": len(state.findings) - len(findings),
            "recent_observations": self._observations(state),
            "completed_tasks": [
                task.id for task in state.tasks if task.status == "COMPLETED"
            ][-self.MAX_COMPLETED_TASKS:],
        }

    def _findings(self, state):
        return [
            {
                "id": finding.id,
                "type": finding.finding_type[:self.MAX_TEXT_LENGTH],
                "status": finding.status,
                "target": finding.target,
            }
            for finding in state.findings[-self.MAX_FINDINGS:]
        ]

    def _observations(self, state):
        result = []
        for observation in state.observations[-self.MAX_OBSERVATIONS:]:
            if observation.data.get("verification_mode") == "DEMO_FIXTURE":
                # Keep the simulation label, but never expose fabricated signals.
                result.append({
                    "task_id": observation.task_id,
                    "execution_status": observation.execution_status,
                    "data": {"verification_mode": "DEMO_FIXTURE"},
                })
                continue
            # Whitelist evidence signals. Raw source, responses, secrets, arbitrary
            # keys and nested objects are never stringified into planner context.
            data = {}
            for key in self.SIGNAL_KEYS:
                value = observation.data.get(key)
                if type(value) is bool:
                    data[key] = value
            status_code = observation.data.get("status_code")
            if type(status_code) is int and 100 <= status_code <= 599:
                data["status_code"] = status_code
            candidates = observation.data.get("potential_findings")
            if isinstance(candidates, list):
                data["potential_findings"] = [
                    value for value in candidates[:10]
                    if isinstance(value, str) and value in {"SQL Injection", "SSRF"}
                ]
            result.append({
                "task_id": observation.task_id,
                "execution_status": observation.execution_status,
                "data": data,
            })
        return result
