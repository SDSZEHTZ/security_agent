from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from models.request import Action


class ToolResult(BaseModel):

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1)

    status: Literal[
        "SUCCESS",
        "ERROR"
    ]

    data: dict[str, Any] = Field(
        default_factory=dict
    )

    error: str | None = None


class ToolContext(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    task_id: str = Field(min_length=1)

    agent: str = Field(min_length=1)

    action: Action

    authorized_root: str | None = None

    authorized_origin: str | None = None