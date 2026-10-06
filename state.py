from models.task import Task


class AgentState:
    def __init__(self, target: str):
        self.target = target
        self.phase = "ANALYZE"
        self.tasks: list[Task] = []
        self.findings: list[dict] = []
        self.evidence: list[dict] = []
        self.observations: list[dict] = []

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)

    def add_observation(self, observation: dict) -> None:
        self.observations.append(observation)
