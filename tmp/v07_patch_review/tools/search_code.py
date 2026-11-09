import stat

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from models.tool import ToolContext

from tools.file_policy import (
    ALLOWED_SOURCE_EXTENSIONS,
    IGNORED_DIR_NAMES,
    MAX_SEARCH_ENTRIES,
    MAX_SEARCH_FILES,
    MAX_SEARCH_MATCHES,
    MAX_SEARCH_TOTAL_BYTES,
    MAX_SOURCE_FILE_BYTES,
    MAX_SNIPPET_CHARS,
    SENSITIVE_FILE_NAMES,
    TraversalStatus,
    get_authorized_root,
    iter_project_files,
    read_bounded_bytes,
)


class SearchCodeArgs(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    query: str = Field(
        min_length=1,
        max_length=100,
    )

    max_matches: int = Field(
        default=30,
        ge=1,
        le=MAX_SEARCH_MATCHES,
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:

        if not value.strip() or "\x00" in value:
            raise ValueError(
                "INVALID_SEARCH_QUERY"
            )

        return value


class SearchCodeTool:

    name = "search_code"

    args_model = SearchCodeArgs

    def execute(
        self,
        args: SearchCodeArgs,
        context: ToolContext,
    ) -> dict:

        root = get_authorized_root(
            context
        )

        matches = []

        traversal = TraversalStatus()

        files_attempted = 0

        files_scanned = 0

        bytes_scanned = 0

        truncated = False

        query = args.query.casefold()

        for candidate in iter_project_files(
            root, max_entries=MAX_SEARCH_ENTRIES, status=traversal,
        ):

            try:

                resolved = candidate.resolve(
                    strict=True
                )

                relative_path = resolved.relative_to(
                    root
                )

            except (OSError, RuntimeError, ValueError):
                truncated = True
                continue

            if any(part.casefold() in IGNORED_DIR_NAMES for part in relative_path.parts[:-1]):
                continue

            if resolved.name.casefold() in SENSITIVE_FILE_NAMES:
                continue

            if resolved.suffix.casefold() not in ALLOWED_SOURCE_EXTENSIONS:
                continue

            try:

                file_stat = resolved.stat()

            except OSError:
                truncated = True
                continue

            if not stat.S_ISREG(file_stat.st_mode):
                continue

            if files_attempted >= MAX_SEARCH_FILES:
                truncated = True
                break

            file_size = file_stat.st_size

            if file_size > MAX_SOURCE_FILE_BYTES:
                truncated = True
                continue

            if (
                bytes_scanned + file_size
                > MAX_SEARCH_TOTAL_BYTES
            ):
                truncated = True
                break

            try:

                files_attempted += 1
                content_bytes = read_bounded_bytes(
                    resolved,
                    min(MAX_SOURCE_FILE_BYTES, MAX_SEARCH_TOTAL_BYTES - bytes_scanned),
                )

            except (OSError, ValueError):
                truncated = True
                continue

            if (
                bytes_scanned + len(content_bytes)
                > MAX_SEARCH_TOTAL_BYTES
            ):
                truncated = True
                break

            bytes_scanned += len(content_bytes)

            files_scanned += 1

            try:

                content = content_bytes.decode(
                    "utf-8"
                )

            except UnicodeDecodeError:
                truncated = True
                continue

            for line_number, line in enumerate(
                content.splitlines(),
                start=1,
            ):

                if query in line.casefold():

                    matches.append({
                        "path": relative_path.as_posix(),
                        "line": line_number,
                        "snippet": line[:MAX_SNIPPET_CHARS],
                    })

                    if len(matches) >= args.max_matches:
                        truncated = True
                        break

            if len(matches) >= args.max_matches:
                break

        return {
            "query": args.query,
            "matches": matches,
            "files_scanned": files_scanned,
            "bytes_scanned": bytes_scanned,
            "truncated": truncated or traversal.truncated,
        }
