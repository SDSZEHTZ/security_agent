from typing import Literal

from pydantic import BaseModel, Field


FindingStatus = Literal[
    "POTENTIAL",
    "CONFIRMED",
    "REJECTED",
    "UNCONFIRMED",
]


class Finding(BaseModel):

    id: str = Field(min_length=1)

    finding_type: str = Field(min_length=1)

    target: str = Field(min_length=1)

    status: FindingStatus = "POTENTIAL"