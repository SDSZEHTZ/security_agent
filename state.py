from models.evidence import Evidence
from models.finding import Finding
from models.observation import Observation
from models.task import Task


class AgentState:
    def __init__(self, target: str):
        self.target = target
        self.phase = "ANALYZE"
        self.tasks: list[Task] = []
        self.findings: list[Finding] = []
        self.evidence: list[Evidence] = []
        self.observations: list[Observation] = []

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)
