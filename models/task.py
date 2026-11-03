from dataclasses import dataclass, field


@dataclass
class Task:
    id: str
    agent: str
    action: str
    target: str

    status: str = "PENDING"

    dependencies: list[str] = field(
        default_factory=list
    )

    finding_id: str | None = None

    block_reason: str | None = None