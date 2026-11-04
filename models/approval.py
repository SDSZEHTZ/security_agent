import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.request import Action


class ApprovalSnapshot(BaseModel):

    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    id: str = Field(min_length=1)

    agent: str = Field(min_length=1)

    action: Action

    target: str = Field(min_length=1)

    arguments_json: str = "{}"

    finding_id: str | None = None

    phase: Literal[
        "ANALYZE",
        "VERIFY",
        "REPORT"
    ] = "ANALYZE"

    dependencies: tuple[str, ...] = ()

    @classmethod
    def from_task(cls, task):

        arguments_json = json.dumps(
            task.arguments,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

        return cls(
            id=task.id,
            agent=task.agent,
            action=task.action,
            target=task.target,
            arguments_json=arguments_json,
            finding_id=task.finding_id,
            phase=task.phase,
            dependencies=tuple(task.dependencies),
        )

    @property
    def arguments(self):
        return json.loads(
            self.arguments_json
        )


class PendingAction(BaseModel):

    action_id: str

    snapshot: ApprovalSnapshot

    status: Literal[
        "WAITING_CONFIRMATION",
        "APPROVED",
        "EXECUTED",
        "REJECTED",
    ] = "WAITING_CONFIRMATION"
