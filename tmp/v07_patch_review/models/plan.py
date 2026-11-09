from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from models.request import Action

Phase = Literal[
    "ANALYZE",
    "VERIFY",
    "REPORT",
]


class PlannedTask(BaseModel):

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)

    agent: str = Field(min_length=1)

    action: Action

    target: str = Field(min_length=1)

    arguments: dict[str, Any] = Field(
        default_factory=dict
    )

    depends_on: list[str] = Field(default_factory=list)

    finding_id: str | None = None


class PlanProposal(BaseModel):

    model_config = ConfigDict(extra="forbid")

    phase: Phase

    summary: str

    tasks: list[PlannedTask]
