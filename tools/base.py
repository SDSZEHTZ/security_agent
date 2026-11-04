from typing import Any, Protocol

from pydantic import BaseModel

from models.tool import ToolContext


class Tool(Protocol):

    name: str

    args_model: type[BaseModel]

    def execute(
        self,
        args: BaseModel,
        context: ToolContext,
    ) -> dict[str, Any]:
        ...