from pydantic import BaseModel


class ToolRegistry:

    def __init__(self):

        self._tools: dict[str, object] = {}


    def register(self, tool: object) -> None:

        name = getattr(tool, "name", None)

        args_model = getattr(tool, "args_model", None)

        execute = getattr(tool, "execute", None)

        if (
            not isinstance(name, str)
            or not name
            or not name.isidentifier()
        ):
            raise ValueError("INVALID_TOOL_NAME")

        if name in self._tools:
            raise ValueError("DUPLICATE_TOOL")

        if (
            not isinstance(args_model, type)
            or not issubclass(args_model, BaseModel)
        ):
            raise ValueError("INVALID_TOOL_ARGS_MODEL")

        if not callable(execute):
            raise ValueError("INVALID_TOOL_IMPLEMENTATION")

        self._tools[name] = tool


    def get(self, name: str) -> object | None:

        return self._tools.get(name)


    def names(self) -> tuple[str, ...]:

        return tuple(self._tools.keys())