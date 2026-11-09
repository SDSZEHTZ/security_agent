from models.plan import PlanProposal, PlannedTask


class DemoPlanner:
    """Deterministic offline demonstration of the same phase-planning contract."""

    def plan_phase(self, goal, phase, context):
        target = context["authorized_target"]
        tasks = []
        if phase == "ANALYZE":
            tasks.append(PlannedTask(
                key="analysis", agent="CodeAnalysisAgent",
                action="analyze_code", target=target,
                arguments={"query": "execute(", "max_matches": 20},
            ))
        elif phase == "VERIFY":
            actions = {"SQL Injection": "verify_sqli", "SSRF": "verify_ssrf"}
            for finding in context["findings"]:
                if finding["status"] in {"POTENTIAL", "UNCONFIRMED"} and finding["type"] in actions:
                    tasks.append(PlannedTask(
                        key=f"verify_{finding['id']}", agent="VerificationAgent",
                        action=actions[finding["type"]], target=target,
                        finding_id=finding["id"],
                    ))
        elif phase == "REPORT":
            tasks.append(PlannedTask(
                key="report", agent="ReportAgent", action="generate_report", target=target,
            ))
        return PlanProposal(phase=phase, summary="Offline demonstration", tasks=tasks[:10])
