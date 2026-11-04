from dataclasses import dataclass, field
from typing import Any


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

    phase: str = "ANALYZE"

    arguments: dict[str, Any] = field(
        default_factory=dict
    )