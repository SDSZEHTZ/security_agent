import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from models.tool import ToolContext
from tools.file_policy import read_bounded_bytes
from tools.read_source import ReadSourceArgs, ReadSourceTool


class ReadSourceTests(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = Path(temp_dir.name).resolve()
        (self.root / "src").mkdir()
        self.content = "def hello():\n    return '你好'\n"
        self.source = self.root / "src" / "app.py"
        self.source.write_bytes(self.content.encode("utf-8"))
        self.context = ToolContext(
            task_id="T1", agent="CodeAnalysisAgent", action="read_file",
            authorized_root=str(self.root),
        )
        self.tool = ReadSourceTool()

    def test_reads_utf8_source_with_relative_path_and_byte_count(self):
        result = self.tool.execute(ReadSourceArgs(path="src/app.py"), self.context)
        self.assertEqual(result, {
            "relative_path": "src/app.py", "content": self.content,
            "bytes": len(self.content.encode("utf-8")),
        })

    def test_authorized_root_is_required(self):
        context = self.context.model_copy(update={"authorized_root": None})
        with self.assertRaisesRegex(PermissionError, "^AUTHORIZED_ROOT_REQUIRED$"):
            self.tool.execute(ReadSourceArgs(path="src/app.py"), context)

    def test_missing_or_non_directory_root_is_rejected(self):
        for root, exception, reason in (
            (self.root / "missing", FileNotFoundError, "AUTHORIZED_ROOT_NOT_FOUND"),
            (self.source, NotADirectoryError, "AUTHORIZED_ROOT_NOT_DIRECTORY"),
        ):
            with self.subTest(root=root):
                context = self.context.model_copy(update={"authorized_root": str(root)})
                with self.assertRaisesRegex(exception, f"^{reason}$"):
                    self.tool.execute(ReadSourceArgs(path="src/app.py"), context)

    def test_invalid_argument_schema_is_rejected(self):
        for arguments in ({}, {"path": ""}, {"path": "a" * 241}, {"path": "src/app.py", "url": "x"}):
            with self.subTest(arguments=arguments), self.assertRaises(ValidationError):
                ReadSourceArgs(**arguments)

    def test_unsafe_paths_are_rejected_before_reading(self):
        for path in (
            "../secret.py", "src/../app.py", "/tmp/secret.py", "C:/secret.py",
            "C:secret.py", "//server/share/secret.py", "src\\app.py",
            "src//app.py", "./src/app.py", "src/app.py/", "src/\x00app.py",
        ):
            with self.subTest(path=path), patch("tools.read_source.read_bounded_bytes") as read:
                with self.assertRaises((ValueError, PermissionError)):
                    self.tool.execute(ReadSourceArgs(path=path), self.context)
                read.assert_not_called()

    def test_sensitive_files_and_unsupported_types_are_rejected(self):
        for name in (".env", ".ENV.local", "id_rsa", "id_ed25519", "authorized_keys", "payload.exe"):
            with self.subTest(name=name):
                (self.root / name).write_bytes(b"private data")
                with patch("tools.read_source.read_bounded_bytes") as read:
                    with self.assertRaises(PermissionError):
                        self.tool.execute(ReadSourceArgs(path=name), self.context)
                    read.assert_not_called()

    def test_missing_file_and_directory_are_rejected(self):
        with self.assertRaisesRegex(FileNotFoundError, "^SOURCE_FILE_NOT_FOUND$"):
            self.tool.execute(ReadSourceArgs(path="missing.py"), self.context)
        with self.assertRaisesRegex(ValueError, "^NOT_A_REGULAR_FILE$"):
            self.tool.execute(ReadSourceArgs(path="src"), self.context)

    def test_resolved_path_outside_root_is_rejected_before_reading(self):
        original_resolve = Path.resolve
        outside = self.root.parent / "outside.py"

        def resolve(path, *args, **kwargs):
            if path == self.source:
                return outside
            return original_resolve(path, *args, **kwargs)

        with patch.object(Path, "resolve", autospec=True, side_effect=resolve):
            with patch("tools.read_source.read_bounded_bytes") as read:
                with self.assertRaisesRegex(PermissionError, "^PATH_OUTSIDE_AUTHORIZED_ROOT$"):
                    self.tool.execute(ReadSourceArgs(path="src/app.py"), self.context)
                read.assert_not_called()

    def test_file_size_boundary_is_enforced(self):
        with patch("tools.read_source.MAX_SOURCE_FILE_BYTES", 8):
            self.source.write_bytes(b"a" * 8)
            self.assertEqual(self.tool.execute(ReadSourceArgs(path="src/app.py"), self.context)["bytes"], 8)
            self.source.write_bytes(b"a" * 9)
            with self.assertRaisesRegex(ValueError, "^FILE_TOO_LARGE$"):
                self.tool.execute(ReadSourceArgs(path="src/app.py"), self.context)

    def test_non_utf8_file_is_rejected(self):
        self.source.write_bytes(b"\xff\xfe")
        with self.assertRaisesRegex(ValueError, "^SOURCE_FILE_NOT_UTF8$"):
            self.tool.execute(ReadSourceArgs(path="src/app.py"), self.context)

    def test_bounded_reader_detects_growth_after_size_check(self):
        self.source.write_bytes(b"a" * 9)
        file_stat = SimpleNamespace(st_mode=stat.S_IFREG, st_size=1)
        with patch("tools.file_policy.os.fstat", return_value=file_stat):
            with self.assertRaisesRegex(ValueError, "^FILE_TOO_LARGE$"):
                read_bounded_bytes(self.source, 8)

    def test_bounded_reader_rejects_non_regular_file(self):
        file_stat = SimpleNamespace(st_mode=stat.S_IFIFO, st_size=0)
        with patch("tools.file_policy.os.fstat", return_value=file_stat):
            with self.assertRaisesRegex(ValueError, "^NOT_A_REGULAR_FILE$"):
                read_bounded_bytes(self.source, 8)


if __name__ == "__main__":
    unittest.main()
