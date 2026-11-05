from models.evidence import Evidence
from models.finding import Finding
from models.observation import Observation
from models.task import Task


class AgentState:

    def __init__(
        self,
        target,
        authorized_origin=None,
    ):

        self.target = target
        self.authorized_origin = authorized_origin

        self.phase = "ANALYZE"

        self.tasks: list[Task] = []

        self.findings: list[Finding] = []

        self.evidence: list[Evidence] = []

        self.observations: list[Observation] = []

        self.planned_phases: set[str] = set()

    def add_task(self, task):
        """Compatibility entry point; mutations are owned by StateManager."""
        from runtime.state_manager import StateManager

        StateManager().add_task(self, task)
