import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from models.tool import ToolContext


# 允许读取的源码类型
ALLOWED_SOURCE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go",
    ".java", ".php", ".html", ".css", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".sql",
})

# 敏感文件名
SENSITIVE_FILE_NAMES = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
    "authorized_keys",
})

# 搜索时跳过的目录
IGNORED_DIR_NAMES = frozenset({
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
})


# 资源限制
MAX_SOURCE_FILE_BYTES = 256 * 1024

MAX_SEARCH_FILES = 400

MAX_SEARCH_ENTRIES = 2000

MAX_SEARCH_TOTAL_BYTES = 16 * 1024 * 1024

MAX_SEARCH_MATCHES = 80

MAX_SNIPPET_CHARS = 240


def get_authorized_root(context: ToolContext) -> Path:

    if not context.authorized_root:
        raise PermissionError(
            "AUTHORIZED_ROOT_REQUIRED"
        )

    try:
        root = Path(
            context.authorized_root
        ).expanduser().resolve(strict=True)

    except (OSError, RuntimeError) as exc:
        raise FileNotFoundError(
            "AUTHORIZED_ROOT_NOT_FOUND"
        ) from exc

    if not root.is_dir():
        raise NotADirectoryError(
            "AUTHORIZED_ROOT_NOT_DIRECTORY"
        )

    return root


def resolve_source_path(root: Path, raw_path: str) -> Path:

    if (
        not isinstance(raw_path, str)
        or not raw_path
        or "\x00" in raw_path
    ):
        raise ValueError("INVALID_SOURCE_PATH")

    # 只接受使用 / 分隔的相对路径
    if "\\" in raw_path:
        raise PermissionError(
            "BACKSLASH_PATH_NOT_ALLOWED"
        )

    posix_path = PurePosixPath(raw_path)
    windows_path = PureWindowsPath(raw_path)

    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
    ):
        raise PermissionError(
            "ABSOLUTE_PATH_NOT_ALLOWED"
        )

    parts = raw_path.split("/")

    if any(
        part in {"", ".", ".."}
        for part in parts
    ):
        raise PermissionError(
            "INVALID_RELATIVE_PATH"
        )

    try:
        candidate = (
            root.joinpath(*parts)
            .resolve(strict=True)
        )

    except (OSError, RuntimeError) as exc:
        raise FileNotFoundError(
            "SOURCE_FILE_NOT_FOUND"
        ) from exc

    try:
        candidate.relative_to(root)

    except ValueError as exc:
        raise PermissionError(
            "PATH_OUTSIDE_AUTHORIZED_ROOT"
        ) from exc

    if not candidate.is_file():
        raise ValueError(
            "NOT_A_REGULAR_FILE"
        )

    if candidate.name.casefold() in SENSITIVE_FILE_NAMES:
        raise PermissionError(
            "SENSITIVE_FILE_BLOCKED"
        )

    if candidate.suffix.casefold() not in ALLOWED_SOURCE_EXTENSIONS:
        raise PermissionError(
            "FILE_TYPE_NOT_ALLOWED"
        )

    return candidate


def read_bounded_bytes(path: Path, max_bytes: int) -> bytes:

    with path.open("rb") as file_obj:

        file_stat = os.fstat(
            file_obj.fileno()
        )

        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError(
                "NOT_A_REGULAR_FILE"
            )

        if file_stat.st_size > max_bytes:
            raise ValueError(
                "FILE_TOO_LARGE"
            )

        content = file_obj.read(
            max_bytes + 1
        )

    if len(content) > max_bytes:
        raise ValueError(
            "FILE_TOO_LARGE"
        )

    return content


@dataclass
class TraversalStatus:
    entries_seen: int = 0
    truncated: bool = False


def iter_project_files(
    root: Path,
    *,
    max_entries: int = MAX_SEARCH_ENTRIES,
    status: TraversalStatus | None = None,
):
    """Traverse with bounded directory listings, reporting limits and errors."""
    if status is None:
        status = TraversalStatus()
    pending = [root]

    while pending:
        if status.entries_seen >= max_entries:
            status.truncated = True
            return

        current = pending.pop()
        try:
            current = current.resolve(strict=True)
            relative = current.relative_to(root)
            if any(part.casefold() in IGNORED_DIR_NAMES for part in relative.parts):
                continue

            # os.walk materializes a whole directory before callers can limit it.
            # Read at most the remaining budget, including directory entries.
            entries = []
            with os.scandir(current) as iterator:
                while status.entries_seen < max_entries:
                    try:
                        entry = next(iterator)
                    except StopIteration:
                        break
                    status.entries_seen += 1
                    entries.append(entry)
                else:
                    status.truncated = True
        except (OSError, RuntimeError, ValueError):
            status.truncated = True
            continue

        directories = []
        for entry in sorted(entries, key=lambda item: item.name):
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.casefold() in IGNORED_DIR_NAMES or entry.is_symlink():
                        continue
                    attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
                    if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                        continue  # Includes Windows directory junctions.
                    directories.append(Path(entry.path))
                else:
                    yield Path(entry.path)
            except OSError:
                status.truncated = True

        if status.entries_seen >= max_entries:
            return
        pending.extend(reversed(directories))
