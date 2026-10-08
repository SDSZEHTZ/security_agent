from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskRequest(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: str = Field(min_length=1)

    agent: str = Field(min_length=1)

    action: Literal[
        "analyze_code",
        "read_file",
        "verify_sqli",
        "verify_ssrf",
        "execute_command",
        "generate_report",
    ]

    target: str = Field(min_length=1)