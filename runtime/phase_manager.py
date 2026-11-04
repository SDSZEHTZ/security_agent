class PhaseManager:
    PHASES = ["ANALYZE", "VERIFY", "REPORT"]
    TERMINAL_TASK_STATUSES = {"COMPLETED", "FAILED", "BLOCKED", "TIMEOUT"}

    def can_advance(self, state):
        if state.phase not in self.PHASES or state.phase not in state.planned_phases:
            return False
        return all(
            task.status in self.TERMINAL_TASK_STATUSES
            for task in state.tasks if task.phase == state.phase
        )

    def next_phase(self, current_phase):
        index = self.PHASES.index(current_phase)
        return self.PHASES[index + 1] if index + 1 < len(self.PHASES) else "END"
