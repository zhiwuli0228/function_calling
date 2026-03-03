import sys
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.function_calling.logx.grepper import ZGrepOptions, iter_zgrep_lines


class ZGrepTests(unittest.TestCase):
    def test_zgrep_or_and_color(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "collect.log"
            path.write_text("alpha\nERROR boom\ntimeout\nother\n", encoding="utf-8")

            options = ZGrepOptions(
                root=root,
                pattern="timeout",
                or_patterns=["ERROR"],
                name_glob="collect*",
                regex=True,
                fixed=False,
                ignore_case=False,
                line_number=True,
                context_before=0,
                context_after=0,
                max_count=None,
                files_with_matches=False,
                files_without_match=False,
                count_only=False,
                suppress_filename=False,
                force_filename=False,
                include_archives=False,
                color="always",
            )

            lines = list(iter_zgrep_lines(options))
            self.assertEqual(len(lines), 2)
            self.assertTrue(any("ERROR" in line for line in lines))
            self.assertTrue(any("timeout" in line for line in lines))
            self.assertTrue(all("\x1b[01;31m" in line for line in lines))

    def test_zgrep_count(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.log").write_text("hit\nmiss\n", encoding="utf-8")
            (root / "b.log").write_text("miss\n", encoding="utf-8")

            options = ZGrepOptions(
                root=root,
                pattern="hit",
                or_patterns=[],
                name_glob="*.log",
                regex=False,
                fixed=True,
                ignore_case=False,
                line_number=False,
                context_before=0,
                context_after=0,
                max_count=None,
                files_with_matches=False,
                files_without_match=False,
                count_only=True,
                suppress_filename=False,
                force_filename=False,
                include_archives=False,
                color="never",
            )

            lines = sorted(iter_zgrep_lines(options))
            self.assertEqual(len(lines), 2)
            self.assertTrue(any(line.endswith(":1") for line in lines))
            self.assertTrue(any(line.endswith(":0") for line in lines))

    def test_zgrep_context(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "c.log").write_text("a\nb\nHIT\nc\nd\n", encoding="utf-8")

            options = ZGrepOptions(
                root=root,
                pattern="HIT",
                or_patterns=[],
                name_glob="*.log",
                regex=False,
                fixed=True,
                ignore_case=False,
                line_number=True,
                context_before=1,
                context_after=1,
                max_count=None,
                files_with_matches=False,
                files_without_match=False,
                count_only=False,
                suppress_filename=False,
                force_filename=False,
                include_archives=False,
                color="never",
            )

            lines = list(iter_zgrep_lines(options))
            self.assertEqual(len(lines), 3)
            file_prefix = str(root / "c.log")
            self.assertTrue(any(f"{file_prefix}-2-" in line for line in lines))
            self.assertTrue(any(f"{file_prefix}:3:" in line for line in lines))
            self.assertTrue(any(f"{file_prefix}-4-" in line for line in lines))

    def test_zgrep_list_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "hit.log").write_text("hit\n", encoding="utf-8")
            (root / "miss.log").write_text("no\n", encoding="utf-8")

            options = ZGrepOptions(
                root=root,
                pattern="hit",
                or_patterns=[],
                name_glob="*.log",
                regex=False,
                fixed=True,
                ignore_case=False,
                line_number=False,
                context_before=0,
                context_after=0,
                max_count=None,
                files_with_matches=True,
                files_without_match=False,
                count_only=False,
                suppress_filename=False,
                force_filename=False,
                include_archives=False,
                color="never",
            )

            lines = list(iter_zgrep_lines(options))
            self.assertEqual(len(lines), 1)
            self.assertTrue(lines[0].endswith("hit.log"))

    def test_zgrep_files_without_match(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "hit.log").write_text("hit\n", encoding="utf-8")
            (root / "miss.log").write_text("no\n", encoding="utf-8")

            options = ZGrepOptions(
                root=root,
                pattern="hit",
                or_patterns=[],
                name_glob="hit.log",
                regex=False,
                fixed=True,
                ignore_case=False,
                line_number=False,
                context_before=0,
                context_after=0,
                max_count=None,
                files_with_matches=False,
                files_without_match=True,
                count_only=False,
                suppress_filename=False,
                force_filename=False,
                include_archives=False,
                color="never",
            )

            lines = list(iter_zgrep_lines(options))
            self.assertEqual(len(lines), 0)

            options.name_glob = "*.log"
            lines = list(iter_zgrep_lines(options))
            self.assertEqual(len(lines), 1)
            self.assertTrue(lines[0].endswith("miss.log"))

    def test_zgrep_max_count(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.log").write_text("hit\nhit\nhit\n", encoding="utf-8")

            options = ZGrepOptions(
                root=root,
                pattern="hit",
                or_patterns=[],
                name_glob="*.log",
                regex=False,
                fixed=True,
                ignore_case=False,
                line_number=False,
                context_before=0,
                context_after=0,
                max_count=2,
                files_with_matches=False,
                files_without_match=False,
                count_only=False,
                suppress_filename=True,
                force_filename=False,
                include_archives=False,
                color="never",
            )

            lines = list(iter_zgrep_lines(options))
            self.assertEqual(len(lines), 2)

    def test_zgrep_filename_flags(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.log").write_text("hit\n", encoding="utf-8")

            options_h = ZGrepOptions(
                root=root,
                pattern="hit",
                or_patterns=[],
                name_glob="*.log",
                regex=False,
                fixed=True,
                ignore_case=False,
                line_number=False,
                context_before=0,
                context_after=0,
                max_count=None,
                files_with_matches=False,
                files_without_match=False,
                count_only=False,
                suppress_filename=True,
                force_filename=False,
                include_archives=False,
                color="never",
            )

            options_H = ZGrepOptions(
                root=root,
                pattern="hit",
                or_patterns=[],
                name_glob="*.log",
                regex=False,
                fixed=True,
                ignore_case=False,
                line_number=False,
                context_before=0,
                context_after=0,
                max_count=None,
                files_with_matches=False,
                files_without_match=False,
                count_only=False,
                suppress_filename=False,
                force_filename=True,
                include_archives=False,
                color="never",
            )

            lines_h = list(iter_zgrep_lines(options_h))
            lines_H = list(iter_zgrep_lines(options_H))
            self.assertEqual(len(lines_h), 1)
            self.assertEqual(len(lines_H), 1)
            self.assertEqual(lines_h[0], "hit")
            self.assertTrue(lines_H[0].endswith(":hit"))


if __name__ == "__main__":
    unittest.main()
