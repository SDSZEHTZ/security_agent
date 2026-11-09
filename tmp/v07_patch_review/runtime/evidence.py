from models.evidence import Evidence


class EvidenceExtractor:

    def __init__(self):

        self._next_id = 1


    def extract(
        self,
        observation,
        task,
    ):

        if observation.execution_status != "SUCCESS":
            return []

        # Built-in VerificationAgent fixtures are illustrative only. Their
        # simulated SQL error / callback fields must not become Evidence.
        # This marker is not an attestation of real-world tool provenance.
        if observation.data.get("verification_mode") == "DEMO_FIXTURE":
            return []

        if task.finding_id is None:
            return []

        if task.action == "verify_sqli":

            return self._extract_sqli(
                observation,
                task,
            )

        if task.action == "verify_ssrf":

            return self._extract_ssrf(
                observation,
                task,
            )

        return []


    def _new_id(self):

        evidence_id = (
            f"E{self._next_id:03d}"
        )

        self._next_id += 1

        return evidence_id

    def _extract_sqli(
        self,
        observation,
        task,
    ):

        evidence = []

        response = str(
            observation.data.get(
                "response",
                "",
            )
        )

        if "SQL syntax" in response:

            evidence.append(
                Evidence(
                    id=self._new_id(),
                    finding_id=task.finding_id,
                    task_id=task.id,
                    evidence_type=
                        "SQL_ERROR_SIGNAL",
                    value=
                        "Response contains SQL syntax error",
                    strength="MEDIUM",
                )
            )

        if observation.data.get(
            "boolean_difference"
        ) is True:

            evidence.append(
                Evidence(
                    id=self._new_id(),
                    finding_id=task.finding_id,
                    task_id=task.id,
                    evidence_type=
                        "BOOLEAN_RESPONSE_DIFFERENCE",
                    value=
                        "Boolean payload changed application response",
                    strength="STRONG",
                )
            )

        return evidence

    def _extract_ssrf(
        self,
        observation,
        task,
    ):

        evidence = []

        if observation.data.get(
            "callback_received"
        ) is True:

            evidence.append(
                Evidence(
                    id=self._new_id(),
                    finding_id=task.finding_id,
                    task_id=task.id,
                    evidence_type=
                        "OUT_OF_BAND_CALLBACK",
                    value=
                        "Verification callback was received",
                    strength="STRONG",
                )
            )

        elif observation.data.get(
            "request_completed"
        ) is True:

            evidence.append(
                Evidence(
                    id=self._new_id(),
                    finding_id=task.finding_id,
                    task_id=task.id,
                    evidence_type=
                        "REQUEST_COMPLETED",
                    value=
                        "Application reported request completion",
                    strength="WEAK",
                )
            )

        return evidence
    
