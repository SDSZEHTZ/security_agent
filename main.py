import json

from agents.code_analysis import CodeAnalysisAgent
from agents.verification import VerificationAgent
from models.task import Task
from runtime.registry import AgentRegistry
from runtime.supervisor import Supervisor
from state import AgentState


def main() -> None:
    state = AgentState(target="./demo_app")

    registry = AgentRegistry()
    registry.register("CodeAnalysisAgent", CodeAnalysisAgent(), ["analyze_code"])
    registry.register("VerificationAgent", VerificationAgent(), ["verify_sqli"])
    supervisor = Supervisor(registry)

    task = Task(
        id="T1",
        agent="CodeAnalysisAgent",
        action="analyze_code",
        target=state.target,
    )
    state.add_task(task)
    result = supervisor.delegate(task, state)

    print("\n=== Result ===")
    print(json.dumps(result, indent=4, ensure_ascii=False))
    print("\n=== Task Status ===")
    print(task.status)
    print("\n=== Observations ===")
    print(json.dumps(state.observations, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
