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

    finding_id: str | None = None

    phase: Literal["ANALYZE", "VERIFY", "REPORT"] = "ANALYZE"

    dependencies: tuple[str, ...] = ()


class PendingAction(BaseModel):

    action_id: str

    snapshot: ApprovalSnapshot

    status: Literal[
        "WAITING_CONFIRMATION",
        "APPROVED",
        "EXECUTED",
        "REJECTED",
    ] = "WAITING_CONFIRMATION"
