from pydantic import BaseModel, ConfigDict, Field

from models.tool import ToolContext

from tools.file_policy import (
    MAX_SOURCE_FILE_BYTES,
    get_authorized_root,
    read_bounded_bytes,
    resolve_source_path,
)


class ReadSourceArgs(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    path: str = Field(
        min_length=1,
        max_length=240,
    )


class ReadSourceTool:

    name = "read_source"

    args_model = ReadSourceArgs

    def execute(
        self,
        args: ReadSourceArgs,
        context: ToolContext,
    ) -> dict:

        root = get_authorized_root(
            context
        )

        source_path = resolve_source_path(
            root,
            args.path,
        )

        content_bytes = read_bounded_bytes(
            source_path,
            MAX_SOURCE_FILE_BYTES,
        )

        try:

            content = content_bytes.decode(
                "utf-8"
            )

        except UnicodeDecodeError as exc:

            raise ValueError(
                "SOURCE_FILE_NOT_UTF8"
            ) from exc

        return {
            "relative_path": source_path.relative_to(root).as_posix(),
            "content": content,
            "bytes": len(content_bytes),
        }