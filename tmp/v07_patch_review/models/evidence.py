from typing import Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):

    id: str = Field(min_length=1)

    finding_id: str = Field(min_length=1)

    task_id: str = Field(min_length=1)

    evidence_type: str = Field(min_length=1)

    value: str

    strength: Literal[
        "WEAK",
        "MEDIUM",
        "STRONG",
    ]