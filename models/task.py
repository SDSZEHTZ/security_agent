from dataclasses import dataclass


@dataclass
class Task:
    id: str
    agent: str
    action: str
    target: str
    status: str = "PENDING"
