from typing import Literal

from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from models.tool import ToolContext


MAX_HTTP_RESPONSE_BYTES = 64 * 1024

HTTP_TIMEOUT_SECONDS = 3


class ControlledHttpArgs(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    path: str = Field(
        default="/",
        min_length=1,
        max_length=200,
    )

    method: Literal[
        "GET",
        "HEAD",
    ] = "GET"

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:

        if (
            not value.startswith("/")
            or value.startswith("//")
        ):
            raise ValueError(
                "PATH_MUST_BE_ORIGIN_RELATIVE"
            )

        if (
            "\\" in value
            or "?" in value
            or "#" in value
        ):
            raise ValueError(
                "INVALID_HTTP_PATH"
            )

        if any(
            ord(char) < 32 or ord(char) == 127
            for char in value
        ):
            raise ValueError(
                "CONTROL_CHARACTER_NOT_ALLOWED"
            )

        decoded = value

        for _ in range(10):

            next_value = unquote(decoded)

            if next_value == decoded:
                break

            decoded = next_value

        else:
            raise ValueError(
                "PATH_ENCODING_TOO_DEEP"
            )

        if any(ord(char) < 32 or ord(char) == 127 for char in decoded):
            raise ValueError("CONTROL_CHARACTER_NOT_ALLOWED")

        if "?" in decoded or "#" in decoded:
            raise ValueError("INVALID_HTTP_PATH")

        if (
            decoded.startswith("//")
            or "://" in decoded
            or "\\" in decoded
            or any(
                part in {".", ".."}
                for part in decoded.split("/")
            )
        ):
            raise ValueError(
                "PATH_TRAVERSAL_BLOCKED"
            )

        return value


class NoRedirectHandler(HTTPRedirectHandler):

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):

        return None


class ControlledHttpCheckTool:

    name = "controlled_http_check"

    args_model = ControlledHttpArgs

    def _get_authorized_origin(
        self,
        context: ToolContext,
    ) -> str:

        if not context.authorized_origin:
            raise PermissionError(
                "AUTHORIZED_ORIGIN_REQUIRED"
            )

        # urlsplit silently removes some control characters; reject them first.
        if any(
            char.isspace() or ord(char) < 32 or ord(char) == 127
            for char in context.authorized_origin
        ):
            raise ValueError("AUTHORIZED_ORIGIN_MUST_BE_ORIGIN")

        try:

            parsed = urlsplit(
                context.authorized_origin
            )

            port = parsed.port

        except ValueError as exc:

            raise ValueError(
                "INVALID_AUTHORIZED_ORIGIN"
            ) from exc

        scheme = parsed.scheme.lower()

        if (
            scheme not in {"http", "https"}
            or not parsed.hostname
            or any(
                char.isspace()
                for char in parsed.netloc
            )
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):

            raise ValueError(
                "AUTHORIZED_ORIGIN_MUST_BE_ORIGIN"
            )

        # parsed.port 已经完成端口合法性检查
        _ = port

        return f"{scheme}://{parsed.netloc}"


    def execute(
        self,
        args: ControlledHttpArgs,
        context: ToolContext,
    ) -> dict:

        origin = self._get_authorized_origin(
            context
        )

        url = origin + args.path

        opener = build_opener(
            ProxyHandler({}),
            NoRedirectHandler(),
        )

        request = Request(
            url,
            method=args.method,
            headers={
                "User-Agent": "SecurityAgentRuntime/0.7"
            },
        )

        try:

            with opener.open(
                request,
                timeout=HTTP_TIMEOUT_SECONDS,
            ) as response:

                body = (
                    response.read(
                        MAX_HTTP_RESPONSE_BYTES + 1
                    )
                    if args.method == "GET"
                    else b""
                )

                return {
                    "url": url,
                    "method": args.method,
                    "status_code": response.status,
                    "content_type": response.headers.get(
                        "Content-Type"
                    ),
                    "body_bytes_read": min(
                        len(body),
                        MAX_HTTP_RESPONSE_BYTES,
                    ),
                    "truncated": (
                        len(body) > MAX_HTTP_RESPONSE_BYTES
                    ),
                    "redirect_not_followed": False,
                }

        except HTTPError as exc:

            try:
                return {
                    "url": url,
                    "method": args.method,
                    "status_code": exc.code,
                    "content_type": (
                        exc.headers.get("Content-Type")
                        if exc.headers
                        else None
                    ),
                    "body_bytes_read": 0,
                    "truncated": False,
                    "redirect_not_followed": (
                        300 <= exc.code < 400
                    ),
                }
            finally:
                exc.close()
