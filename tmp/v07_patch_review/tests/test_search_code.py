import os
import stat
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from models.tool import ToolContext
from tools.search_code import SearchCodeArgs, SearchCodeTool


class SearchCodeTests(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = Path(temp_dir.name).resolve()
        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_bytes(b"def run():\n    eval(user_input)\n")
        (self.root / "src" / "other.js").write_bytes(b"const x = 'EVAL(';\n")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "ignored.py").write_bytes(b"eval(secret)\n")
        self.context = ToolContext(
            task_id="T1", agent="CodeAnalysisAgent", action="analyze_code",
            authorized_root=str(self.root),
        )
        self.tool = SearchCodeTool()

    def search(self, **arguments):
        return self.tool.execute(SearchCodeArgs(query="eval(", **arguments), self.context)

    def test_case_insensitive_search_returns_relative_paths_and_line_numbers(self):
        result = self.search()
        self.assertEqual(result["matches"], [
            {"path": "src/app.py", "line": 2, "snippet": "    eval(user_input)"},
            {"path": "src/other.js", "line": 1, "snippet": "const x = 'EVAL(';"},
        ])
        self.assertEqual(result["files_scanned"], 2)
        self.assertFalse(result["truncated"])

    def test_query_is_literal_and_not_a_regular_expression(self):
        result = self.tool.execute(SearchCodeArgs(query=".*"), self.context)
        self.assertEqual(result["matches"], [])
        self.assertFalse(result["truncated"])

    def test_invalid_queries_limits_and_extra_arguments_are_rejected(self):
        for arguments in (
            {"query": ""}, {"query": "   "}, {"query": "\x00"}, {"query": "a" * 101},
            {"query": "eval(", "max_matches": 0}, {"query": "eval(", "max_matches": 81},
            {"query": "eval(", "root": "elsewhere"},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValidationError):
                SearchCodeArgs(**arguments)

    def test_match_and_snippet_limits_are_reported(self):
        (self.root / "src" / "app.py").write_bytes(b"eval(" + b"x" * 1000)
        result = self.search(max_matches=1)
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(len(result["matches"][0]["snippet"]), 240)
        self.assertTrue(result["truncated"])

    def test_file_limit_stops_reads_and_marks_truncation(self):
        with patch("tools.search_code.MAX_SEARCH_FILES", 1):
            result = self.search()
        self.assertEqual(result["files_scanned"], 1)
        self.assertEqual(len(result["matches"]), 1)
        self.assertTrue(result["truncated"])

    def test_unreadable_files_also_consume_the_read_attempt_limit(self):
        with patch("tools.search_code.MAX_SEARCH_FILES", 1):
            with patch("tools.search_code.read_bounded_bytes", side_effect=PermissionError) as read:
                result = self.search()
        self.assertEqual(read.call_count, 1)
        self.assertTrue(result["truncated"])

    def test_total_byte_limit_is_enforced(self):
        for path in (self.root / "src").iterdir():
            path.write_bytes(b"eval(x)")
        with patch("tools.search_code.MAX_SEARCH_TOTAL_BYTES", 10):
            result = self.search()
        self.assertEqual(result["bytes_scanned"], 7)
        self.assertEqual(result["files_scanned"], 1)
        self.assertTrue(result["truncated"])

    def test_growth_during_read_cannot_exceed_remaining_byte_budget(self):
        (self.root / "src" / "app.py").write_bytes(b"x")
        with patch("tools.search_code.MAX_SEARCH_TOTAL_BYTES", 3):
            with patch("tools.search_code.read_bounded_bytes", return_value=b"eval(x)") as read:
                result = self.search()
        self.assertLessEqual(read.call_args.args[1], 3)
        self.assertLessEqual(result["bytes_scanned"], 3)
        self.assertTrue(result["truncated"])

    def test_empty_directories_consume_entry_budget(self):
        empty_root = self.root / "empty"
        empty_root.mkdir()
        for index in range(8):
            (empty_root / str(index)).mkdir()
        context = self.context.model_copy(update={"authorized_root": str(empty_root)})
        original_scandir = os.scandir
        entries_seen = []

        @contextmanager
        def scandir(path):
            with original_scandir(path) as entries:
                def counted():
                    for entry in entries:
                        entries_seen.append(entry.name)
                        yield entry
                yield counted()

        with patch("tools.file_policy.os.scandir", side_effect=scandir):
            with patch("tools.search_code.MAX_SEARCH_ENTRIES", 3):
                result = self.tool.execute(SearchCodeArgs(query="eval("), context)
        self.assertEqual(len(entries_seen), 3)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["files_scanned"], 0)

    def test_windows_directory_junction_is_not_followed(self):
        entry = SimpleNamespace(
            name="junction", path=str(self.root / "junction"),
            is_dir=lambda **kwargs: True, is_symlink=lambda: False,
            stat=lambda **kwargs: SimpleNamespace(
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
            ),
        )
        with patch("tools.file_policy.os.scandir") as scandir:
            scandir.return_value.__enter__.return_value = iter([entry])
            with patch("tools.search_code.read_bounded_bytes") as read:
                result = self.search()
            read.assert_not_called()
        scandir.assert_called_once()
        self.assertFalse(result["truncated"])

    def test_deep_directory_traversal_is_bounded(self):
        chain_root = self.root / "chain"
        chain_root.mkdir()
        current = chain_root
        for _ in range(8):
            current = current / "child"
            current.mkdir()
        context = self.context.model_copy(update={"authorized_root": str(chain_root)})
        with patch("tools.file_policy.os.scandir", wraps=os.scandir) as scandir:
            with patch("tools.search_code.MAX_SEARCH_ENTRIES", 3):
                result = self.tool.execute(SearchCodeArgs(query="eval("), context)
        self.assertLessEqual(scandir.call_count, 4)
        self.assertTrue(result["truncated"])

    def test_read_errors_mark_results_incomplete(self):
        with patch("tools.search_code.read_bounded_bytes", side_effect=PermissionError):
            result = self.search()
        self.assertEqual(result["files_scanned"], 0)
        self.assertTrue(result["truncated"])

    def test_directory_read_errors_mark_results_incomplete(self):
        original_scandir = os.scandir

        def scandir(path):
            if Path(path) == self.root / "src":
                raise PermissionError("unreadable directory")
            return original_scandir(path)

        with patch("tools.file_policy.os.scandir", side_effect=scandir):
            result = self.search()
        self.assertTrue(result["truncated"])

    def test_non_utf8_files_mark_results_incomplete(self):
        (self.root / "src" / "app.py").write_bytes(b"\xff\xfe")
        result = self.search()
        self.assertEqual(len(result["matches"]), 1)
        self.assertTrue(result["truncated"])

    def test_oversized_files_mark_results_incomplete(self):
        (self.root / "src" / "app.py").write_bytes(b"x" * 100)
        with patch("tools.search_code.MAX_SOURCE_FILE_BYTES", 40):
            result = self.search()
        self.assertEqual(len(result["matches"]), 1)
        self.assertTrue(result["truncated"])

    def test_policy_exclusions_are_skipped(self):
        (self.root / ".env").write_bytes(b"eval(secret)")
        (self.root / "binary.exe").write_bytes(b"eval(secret)")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "ignored.py").write_bytes(b"eval(secret)")
        result = self.search()
        self.assertEqual(len(result["matches"]), 2)
        self.assertFalse(result["truncated"])

    def test_file_resolving_into_ignored_directory_is_skipped(self):
        alias = self.root / "alias.py"
        alias.write_bytes(b"placeholder")
        original_resolve = Path.resolve

        def resolve(path, *args, **kwargs):
            if path == alias:
                return self.root / ".git" / "ignored.py"
            return original_resolve(path, *args, **kwargs)

        with patch.object(Path, "resolve", autospec=True, side_effect=resolve):
            result = self.search()
        self.assertEqual(len(result["matches"]), 2)
        self.assertTrue(all(not item["path"].startswith(".git/") for item in result["matches"]))

    def test_outside_resolved_file_is_never_read(self):
        original_resolve = Path.resolve

        def resolve(path, *args, **kwargs):
            if path == self.root / "src" / "app.py":
                return self.root.parent / "outside.py"
            return original_resolve(path, *args, **kwargs)

        with patch.object(Path, "resolve", autospec=True, side_effect=resolve):
            result = self.search()
        self.assertEqual([match["path"] for match in result["matches"]], ["src/other.js"])


if __name__ == "__main__":
    unittest.main()
