from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Action = Literal[
    "analyze_code",
    "read_file",
    "verify_sqli",
    "verify_ssrf",
    "execute_command",
    "generate_report",
]


class TaskRequest(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: str = Field(min_length=1)

    agent: str = Field(min_length=1)

    action: Action

    target: str = Field(min_length=1)

    phase: Literal["ANALYZE", "VERIFY", "REPORT"] = "ANALYZE"
