class StateManager:

    ALLOWED_FINDING_TRANSITIONS = {

        "POTENTIAL": {
            "CONFIRMED",
            "REJECTED",
            "UNCONFIRMED",
        },

        "UNCONFIRMED": {
            "CONFIRMED",
            "REJECTED",
        },

        "CONFIRMED": set(),

        "REJECTED": set(),
    }


    def add_observation(
        self,
        state,
        observation,
    ):

        state.observations.append(
            observation
        )


    def add_evidence(
        self,
        state,
        evidence,
    ):

        state.evidence.append(
            evidence
        )


    def add_finding(
        self,
        state,
        finding,
    ):

        state.findings.append(
            finding
        )


    def update_task_status(
        self,
        state,
        task_id,
        new_status,
    ):

        task = self.find_task(
            state,
            task_id,
        )

        if task is None:
            raise ValueError(
                "UNKNOWN_TASK"
            )

        task.status = new_status


    def update_finding_status(
        self,
        state,
        finding_id,
        new_status,
    ):

        finding = self.find_finding(
            state,
            finding_id,
        )

        if finding is None:
            raise ValueError(
                "UNKNOWN_FINDING"
            )

        current = finding.status

        allowed = (
            self.ALLOWED_FINDING_TRANSITIONS
            .get(
                current,
                set(),
            )
        )

        if new_status == current:
            return

        if new_status not in allowed:

            raise ValueError(
                "INVALID_FINDING_TRANSITION"
            )

        finding.status = new_status


    def find_task(
        self,
        state,
        task_id,
    ):

        for task in state.tasks:

            if task.id == task_id:
                return task

        return None


    def find_finding(
        self,
        state,
        finding_id,
    ):

        for finding in state.findings:

            if finding.id == finding_id:
                return finding

        return None

    def add_task(self, state, task):
        state.tasks.append(task)

    def mark_phase_planned(self, state, phase):
        if phase != state.phase or phase not in {"ANALYZE", "VERIFY", "REPORT"}:
            raise ValueError("INVALID_PLAN_PHASE")
        state.planned_phases.add(phase)

    def update_phase(self, state, phase):
        from runtime.phase_manager import PhaseManager

        manager = PhaseManager()
        if not manager.can_advance(state) or manager.next_phase(state.phase) != phase:
            raise ValueError("INVALID_PHASE_TRANSITION")
        state.phase = phase

    def record_potential_findings(self, state, task, observation):
        """Only runtime creates finding IDs, targets and initial statuses."""
        from models.finding import Finding

        if task.action != "analyze_code" or observation.execution_status != "SUCCESS":
            return
        candidates = observation.data.get("potential_findings", [])
        if not isinstance(candidates, list):
            return
        for candidate in candidates[:10]:
            if not isinstance(candidate, str) or candidate not in {"SQL Injection", "SSRF"}:
                continue
            if any(f.finding_type == candidate and f.target == task.target for f in state.findings):
                continue
            existing_ids = {f.id for f in state.findings}
            number = 1
            while f"F{number}" in existing_ids:
                number += 1
            self.add_finding(state, Finding(
                id=f"F{number}", finding_type=candidate, target=task.target,
            ))
