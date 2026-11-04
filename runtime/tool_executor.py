from pydantic import ValidationError

from models.tool import ToolContext, ToolResult
from runtime.tool_registry import ToolRegistry


class ToolExecutionDenied(PermissionError):
    pass


class ToolArgumentsInvalid(ValueError):
    pass


class ToolExecutor:

    def __init__(
        self,
        registry: ToolRegistry,
        action_tool_allowlist: dict,
    ):

        self.registry = registry

        self._action_tool_allowlist = {}

        for key, tool_names in action_tool_allowlist.items():

            if (
                not isinstance(key, tuple)
                or len(key) != 2
            ):
                raise ValueError("INVALID_ALLOWLIST_KEY")

            agent, action = key

            if not isinstance(agent, str) or not agent:
                raise ValueError("INVALID_AGENT_NAME")

            if not isinstance(action, str) or not action:
                raise ValueError("INVALID_ACTION_NAME")

            if isinstance(tool_names, (str, bytes)):
                raise ValueError("INVALID_TOOL_ALLOWLIST")

            try:
                names = frozenset(tool_names)
            except TypeError as exc:
                raise ValueError("INVALID_TOOL_ALLOWLIST") from exc

            if any(
                not isinstance(name, str) or not name or not name.isidentifier()
                for name in names
            ):
                raise ValueError("INVALID_TOOL_NAME")

            self._action_tool_allowlist[key] = names


    def execute(
        self,
        tool_name: str,
        arguments: dict,
        context: ToolContext,
    ) -> ToolResult:

        if not isinstance(context, ToolContext):
            raise TypeError("INVALID_TOOL_CONTEXT")

        if not isinstance(tool_name, str) or not tool_name:
            raise ToolExecutionDenied("UNKNOWN_TOOL")

        key = (
            context.agent,
            context.action,
        )

        allowed_tools = self._action_tool_allowlist.get(
            key,
            frozenset(),
        )

        if tool_name not in allowed_tools:

            raise ToolExecutionDenied(
                "TOOL_NOT_ALLOWED_FOR_ACTION"
            )

        tool = self.registry.get(tool_name)

        if tool is None:

            raise ToolExecutionDenied(
                "UNKNOWN_TOOL"
            )

        # Require raw parameters so prebuilt models cannot bypass validation.
        if not isinstance(arguments, dict):
            raise ToolArgumentsInvalid("INVALID_TOOL_ARGUMENTS")

        try:

            parsed_arguments = (
                tool.args_model.model_validate(
                    arguments
                )
            )

        except ValidationError as exc:

            raise ToolArgumentsInvalid(
                "INVALID_TOOL_ARGUMENTS"
            ) from exc

        try:

            raw_data = tool.execute(
                parsed_arguments,
                context,
            )

        except Exception as exc:

            return ToolResult(
                tool_name=tool_name,
                status="ERROR",
                error=type(exc).__name__,
            )

        if not isinstance(raw_data, dict):

            return ToolResult(
                tool_name=tool_name,
                status="ERROR",
                error="INVALID_TOOL_RESULT",
            )

        try:
            return ToolResult(
                tool_name=tool_name,
                status="SUCCESS",
                data=raw_data,
            )
        except ValidationError:
            return ToolResult(
                tool_name=tool_name,
                status="ERROR",
                error="INVALID_TOOL_RESULT",
            )
