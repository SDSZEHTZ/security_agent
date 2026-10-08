import json

from agents.verification import VerificationAgent

from models.finding import Finding
from models.task import Task

from runtime.registry import AgentRegistry
from runtime.supervisor import Supervisor

from state import AgentState


def main():

    state = AgentState(
        target="./demo_app"
    )

    registry = AgentRegistry()

    registry.register(
        "VerificationAgent",
        VerificationAgent(),
        [
            "verify_sqli",
            "verify_ssrf",
        ]
    )

    supervisor = Supervisor(
        registry
    )

    state.phase = "VERIFY"

    finding = Finding(
        id="F1",
        finding_type="SQL Injection",
        target=state.target,
    )

    supervisor.state_manager.add_finding(
        state,
        finding,
    )

    task = Task(
        id="T2",
        agent="VerificationAgent",
        action="verify_sqli",
        target=state.target,
        finding_id=finding.id,
    )

    state.add_task(task)

    result = supervisor.delegate(
        task,
        state
    )

    print("\n=== Result ===")
    print(json.dumps(result.model_dump(), indent=4, ensure_ascii=False))

    print("\n=== Task Status ===")
    print(task.status)

    print("\n=== Observations ===")
    print(json.dumps(
        [item.model_dump() for item in state.observations],
        indent=4,
        ensure_ascii=False,
    ))

    print("\n=== Evidence ===")
    print(json.dumps(
        [item.model_dump() for item in state.evidence],
        indent=4,
        ensure_ascii=False,
    ))

    print("\n=== Findings ===")
    print(json.dumps(
        [item.model_dump() for item in state.findings],
        indent=4,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
