class FindingEvaluator:

    def evaluate(
        self,
        finding,
        evidence_list,
    ):

        related = [
            evidence
            for evidence in evidence_list
            if (
                evidence.finding_id
                == finding.id
            )
        ]

        if any(
            evidence.strength == "STRONG"
            for evidence in related
        ):
            return "CONFIRMED"

        if related:
            return "UNCONFIRMED"

        return "UNCONFIRMED"