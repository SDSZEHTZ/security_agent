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