class AgentRegistry:
    def __init__(self):
        self.agents: dict[str, dict] = {}

    def register(self, name: str, agent: object, capabilities: list[str]) -> None:
        self.agents[name] = {
            "instance": agent,
            "capabilities": list(capabilities),
        }

    def get(self, name: str) -> dict | None:
        return self.agents.get(name)
