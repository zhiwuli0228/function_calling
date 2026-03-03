from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .grepper import GrepOptions, ZGrepOptions, iter_grep, iter_zgrep_lines
from .gui import run_gui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="logx", description="Offline log search for local archives.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_grep = sub.add_parser("grep", help="Streaming search without indexing (grep/zgrep style).")
    p_grep.add_argument("--path", default=".", help="Root directory or file to search.")
    p_grep.add_argument("--name", default="*", help="File name glob, e.g. collect*")
    p_grep.add_argument("--keyword", help="Substring keyword.")
    p_grep.add_argument("--regex", help="Regex expression.")
    p_grep.add_argument("--ignore-case", action="store_true", help="Case-insensitive match.")
    p_grep.add_argument("--limit", type=int, default=500, help="Max matches to return.")
    p_grep.add_argument(
        "--no-archives",
        action="store_true",
        help="Skip searching inside .zip/.gz/.tar* archives.",
    )

    p_zgrep = sub.add_parser("zgrep", help="GNU zgrep-like streaming search.", add_help=False)
    p_zgrep.add_argument("pattern", help="Search pattern (regex by default).")
    p_zgrep.add_argument("path", nargs="?", default=".", help="Root directory or file.")
    p_zgrep.add_argument("--help", action="help", help="Show this help message and exit.")
    p_zgrep.add_argument("-n", action="store_true", dest="line_number", help="Show line numbers.")
    p_zgrep.add_argument("-i", action="store_true", dest="ignore_case", help="Ignore case.")
    p_zgrep.add_argument("-F", action="store_true", dest="fixed", help="Fixed string search.")
    p_zgrep.add_argument("-E", action="store_true", dest="extended", help="Extended regex (default).")
    p_zgrep.add_argument("-m", type=int, dest="max_count", help="Stop after NUM matches per file.")
    p_zgrep.add_argument("-l", action="store_true", dest="files_with_matches", help="Print filenames with matches.")
    p_zgrep.add_argument("-L", action="store_true", dest="files_without_match", help="Print filenames without matches.")
    p_zgrep.add_argument("-c", action="store_true", dest="count_only", help="Print match counts.")
    p_zgrep.add_argument("-H", action="store_true", dest="force_filename", help="Always print filenames.")
    p_zgrep.add_argument("-h", action="store_true", dest="suppress_filename", help="Never print filenames.")
    p_zgrep.add_argument("-A", type=int, default=0, dest="after", help="Print NUM lines after matches.")
    p_zgrep.add_argument("-B", type=int, default=0, dest="before", help="Print NUM lines before matches.")
    p_zgrep.add_argument("-C", type=int, default=0, dest="context", help="Print NUM lines of output context.")
    p_zgrep.add_argument("--name", default="*", help="File name glob, e.g. collect*")
    p_zgrep.add_argument("--or", action="append", dest="or_patterns", help="Additional pattern (OR match).")
    p_zgrep.add_argument("--and", action="append", dest="and_patterns", help="Additional pattern (AND match).")
    p_zgrep.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="Highlight matches (default: auto).",
    )
    p_zgrep.add_argument(
        "--no-archives",
        action="store_true",
        help="Skip searching inside .zip/.gz/.tar* archives.",
    )

    sub.add_parser("gui", help="Launch desktop GUI.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "grep":
        options = GrepOptions(
            root=Path(args.path).expanduser().resolve(),
            name_glob=args.name,
            keyword=args.keyword,
            regex=args.regex,
            ignore_case=bool(args.ignore_case),
            limit=max(1, args.limit),
            include_archives=not args.no_archives,
        )
        if not options.keyword and not options.regex:
            print("No keyword/regex specified.")
            return 1
        count = 0
        for match in iter_grep(options):
            print(f"{match.location}:{match.line_no}:{match.line}")
            count += 1
        if count == 0:
            print("No results.")
        return 0

    if args.command == "zgrep":
        if args.files_with_matches and args.files_without_match:
            print("Invalid options: -l and -L cannot be used together.")
            return 1
        if args.count_only and (args.files_with_matches or args.files_without_match):
            print("Invalid options: -c cannot be combined with -l/-L.")
            return 1
        context_before = max(args.before, args.context)
        context_after = max(args.after, args.context)
        options = ZGrepOptions(
            root=Path(args.path).expanduser().resolve(),
            pattern=args.pattern,
            or_patterns=args.or_patterns or [],
            and_patterns=args.and_patterns or [],
            name_glob=args.name,
            regex=not args.fixed,
            fixed=bool(args.fixed),
            ignore_case=bool(args.ignore_case),
            line_number=bool(args.line_number),
            context_before=max(0, context_before),
            context_after=max(0, context_after),
            max_count=args.max_count if args.max_count and args.max_count > 0 else None,
            files_with_matches=bool(args.files_with_matches),
            files_without_match=bool(args.files_without_match),
            count_only=bool(args.count_only),
            suppress_filename=bool(args.suppress_filename),
            force_filename=bool(args.force_filename),
            include_archives=not args.no_archives,
            color=args.color if args.color == "always" else ("auto" if _isatty() else "never"),
        )
        any_out = False
        for line in iter_zgrep_lines(options):
            print(line)
            any_out = True
        if not any_out and not options.count_only:
            print("No results.")
        return 0

    if args.command == "gui":
        run_gui()
        return 0

    parser.print_help()
    return 1


def _isatty() -> bool:
    return sys.stdout.isatty()
