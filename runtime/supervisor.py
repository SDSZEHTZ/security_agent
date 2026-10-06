from models.task import Task
from runtime.registry import AgentRegistry
from state import AgentState


class Supervisor:
    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def delegate(self, task: Task, state: AgentState) -> dict:
        agent_info = self.registry.get(task.agent)

        if agent_info is None:
            return {"status": "DENIED", "reason": "UNKNOWN_AGENT"}

        if task.action not in agent_info["capabilities"]:
            return {"status": "DENIED", "reason": "CAPABILITY_NOT_ALLOWED"}

        task.status = "RUNNING"
        try:
            result = agent_info["instance"].run(task)
        except Exception as exc:
            task.status = "FAILED"
            return {"status": "FAILED", "reason": str(exc)}

        state.add_observation(result)
        task.status = "COMPLETED"
        return result
