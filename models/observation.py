from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Observation(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
    )

    agent: str = Field(min_length=1)

    task_id: str = Field(min_length=1)

    execution_status: Literal[
        "SUCCESS",
        "FAILED",
        "TIMEOUT",
    ]

    data: dict[str, Any]
