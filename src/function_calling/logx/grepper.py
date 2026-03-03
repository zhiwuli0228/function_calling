from __future__ import annotations

import fnmatch
import gzip
import io
import re
import tarfile
import zipfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator


@dataclass
class GrepOptions:
    root: Path
    name_glob: str | None
    keyword: str | None
    regex: str | None
    ignore_case: bool
    limit: int
    include_archives: bool


@dataclass
class GrepMatch:
    location: str
    line_no: int
    line: str


@dataclass
class ZGrepOptions:
    root: Path
    pattern: str
    or_patterns: list[str]
    and_patterns: list[str]
    name_glob: str | None
    regex: bool
    fixed: bool
    ignore_case: bool
    line_number: bool
    context_before: int
    context_after: int
    max_count: int | None
    files_with_matches: bool
    files_without_match: bool
    count_only: bool
    suppress_filename: bool
    force_filename: bool
    include_archives: bool
    color: str


def iter_grep(options: GrepOptions) -> Iterator[GrepMatch]:
    matcher = _build_matcher(options.keyword, options.regex, options.ignore_case)
    if matcher is None:
        return iter(())

    seen = 0
    for path in _iter_targets(options.root, options.name_glob):
        if path.suffix.lower() == ".zip" and options.include_archives:
            for match in _grep_zip(path, matcher, options.ignore_case):
                yield match
                seen += 1
                if seen >= options.limit:
                    return
            continue
        if path.suffix.lower() in {".gz", ".tgz"} and options.include_archives:
            for match in _grep_gzip(path, matcher, options.ignore_case):
                yield match
                seen += 1
                if seen >= options.limit:
                    return
            continue
        if path.suffix.lower() in {".tar", ".tar.gz", ".tar.bz2", ".tar.xz"} and options.include_archives:
            for match in _grep_tar(path, matcher, options.ignore_case):
                yield match
                seen += 1
                if seen >= options.limit:
                    return
            continue

        for match in _grep_file(path, matcher, options.ignore_case):
            yield match
            seen += 1
            if seen >= options.limit:
                return


def iter_zgrep_lines(options: ZGrepOptions) -> Iterator[str]:
    or_patterns = [options.pattern] + list(options.or_patterns or [])
    and_patterns = list(options.and_patterns or [])
    matcher = _build_matcher(
        keywords=None if options.regex else or_patterns,
        regexes=or_patterns if options.regex else None,
        ignore_case=options.ignore_case,
        fixed=options.fixed,
        and_keywords=None if options.regex else and_patterns,
        and_regexes=and_patterns if options.regex else None,
    )
    highlight = _build_highlighter(options)
    if matcher is None:
        return iter(())

    root = options.root.expanduser().resolve()
    show_filename = options.force_filename or (
        not options.suppress_filename and (root.is_dir() or options.include_archives)
    )

    for location, open_func in _iter_sources(root, options.name_glob, options.include_archives):
        match_count = 0
        emitted_any = False
        before_buf: deque[tuple[int, str]] = deque(maxlen=max(0, options.context_before))
        after_remaining = 0
        last_emit_line: int | None = None

        for line_no, line in _iter_text_lines(open_func):
            text = line.rstrip("\n")
            is_match = matcher(text)

            if is_match:
                match_count += 1
                if options.files_without_match:
                    if options.max_count is not None and match_count >= options.max_count:
                        break
                    continue
                if options.files_with_matches:
                    yield location
                    emitted_any = True
                    break
                if options.count_only:
                    pass
                else:
                    if (options.context_before or options.context_after) and last_emit_line is not None:
                        if line_no - last_emit_line > options.context_before + options.context_after + 1:
                            yield "--"
                    if options.context_before:
                        for ctx_no, ctx_line in before_buf:
                            yield _format_line(
                                location,
                                ctx_no,
                                ctx_line,
                                show_filename,
                                options.line_number,
                                is_context=True,
                            )
                    line_out = text
                    if highlight:
                        line_out = highlight(text)
                    yield _format_line(
                        location,
                        line_no,
                        line_out,
                        show_filename,
                        options.line_number,
                        is_context=False,
                    )
                    emitted_any = True
                    after_remaining = options.context_after
                    last_emit_line = line_no
                    before_buf.clear()

                if options.max_count is not None and match_count >= options.max_count:
                    break
                continue

            if options.count_only or options.files_with_matches:
                continue

            if after_remaining > 0:
                yield _format_line(
                    location,
                    line_no,
                    text,
                    show_filename,
                    options.line_number,
                    is_context=True,
                )
                emitted_any = True
                after_remaining -= 1
                last_emit_line = line_no
                continue

            if options.context_before:
                before_buf.append((line_no, text))

        if options.files_without_match and match_count == 0:
            yield location
        elif options.count_only and not options.files_with_matches:
            if show_filename:
                yield f"{location}:{match_count}"
            else:
                yield str(match_count)
        elif options.files_with_matches and emitted_any:
            # already emitted
            pass


def _iter_targets(root: Path, name_glob: str | None) -> Iterator[Path]:
    root = root.expanduser().resolve()
    if root.is_file():
        yield root
        return
    pattern = name_glob or "*"
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if fnmatch.fnmatch(path.name, pattern):
            yield path


def _iter_sources(
    root: Path, name_glob: str | None, include_archives: bool
) -> Iterator[tuple[str, Callable[[], io.BufferedReader | None]]]:
    for path in _iter_targets(root, name_glob):
        suffix = path.suffix.lower()
        if include_archives and suffix == ".zip":
            if not zipfile.is_zipfile(path):
                # Skip invalid or corrupted zip files.
                continue
            with zipfile.ZipFile(path, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    member_name = info.filename
                    member_base = Path(member_name).name
                    if name_glob and not fnmatch.fnmatch(member_base, name_glob):
                        continue

                    def _open(info=info) -> io.BufferedReader:
                        return zf.open(info, "r")

                    yield f"{path}::{member_name}", _open
            continue
        if include_archives and suffix in {".tar", ".tar.gz", ".tar.bz2", ".tar.xz"}:
            try:
                tf = tarfile.open(path, "r:*")
            except tarfile.TarError:
                continue
            with tf:
                for member in tf.getmembers():
                    if not member.isfile():
                        continue
                    member_name = member.name
                    member_base = Path(member_name).name
                    if name_glob and not fnmatch.fnmatch(member_base, name_glob):
                        continue

                    def _open(member=member) -> io.BufferedReader | None:
                        return tf.extractfile(member)

                    yield f"{path}::{member_name}", _open
            continue
        if include_archives and suffix in {".gz", ".tgz"}:
            def _open() -> io.BufferedReader:
                return gzip.open(path, "rb")

            yield str(path), _open
            continue

        def _open_file(path=path) -> io.BufferedReader:
            return path.open("rb")

        yield str(path), _open_file


def _grep_file(path: Path, matcher: Callable[[str], bool], ignore_case: bool) -> Iterator[GrepMatch]:
    location = str(path)
    for line_no, line in _iter_text_lines(lambda: path.open("rb")):
        if matcher(line):
            yield GrepMatch(location=location, line_no=line_no, line=line.rstrip("\n"))


def _grep_gzip(path: Path, matcher: Callable[[str], bool], ignore_case: bool) -> Iterator[GrepMatch]:
    location = str(path)

    def _open() -> io.BufferedReader:
        return gzip.open(path, "rb")

    for line_no, line in _iter_text_lines(_open):
        if matcher(line):
            yield GrepMatch(location=location, line_no=line_no, line=line.rstrip("\n"))


def _grep_zip(path: Path, matcher: Callable[[str], bool], ignore_case: bool) -> Iterator[GrepMatch]:
    with zipfile.ZipFile(path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            member_name = info.filename

            def _open() -> io.BufferedReader:
                return zf.open(info, "r")

            location = f"{path}::{member_name}"
            for line_no, line in _iter_text_lines(_open):
                if matcher(line):
                    yield GrepMatch(location=location, line_no=line_no, line=line.rstrip("\n"))


def _grep_tar(path: Path, matcher: Callable[[str], bool], ignore_case: bool) -> Iterator[GrepMatch]:
    with tarfile.open(path, "r:*") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            member_name = member.name

            def _open() -> io.BufferedReader | None:
                return tf.extractfile(member)

            location = f"{path}::{member_name}"
            for line_no, line in _iter_text_lines(_open):
                if matcher(line):
                    yield GrepMatch(location=location, line_no=line_no, line=line.rstrip("\n"))


def _iter_text_lines(open_func: Callable[[], io.BufferedReader | None]) -> Iterator[tuple[int, str]]:
    for encoding in ("utf-8", "gbk"):
        f = None
        try:
            raw = open_func()
            if raw is None:
                return
            f = io.TextIOWrapper(raw, encoding=encoding)
            for line_no, line in enumerate(f, start=1):
                yield line_no, line
            return
        except UnicodeDecodeError:
            continue
        finally:
            if f is not None:
                f.close()
    raw = open_func()
    if raw is None:
        return
    with io.TextIOWrapper(raw, encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, start=1):
            yield line_no, line


def _build_matcher(
    keywords: list[str] | None,
    regexes: list[str] | None,
    ignore_case: bool,
    fixed: bool = False,
    and_keywords: list[str] | None = None,
    and_regexes: list[str] | None = None,
) -> Callable[[str], bool] | None:
    if not keywords and not regexes:
        return None
    if regexes:
        flags = re.IGNORECASE if ignore_case else 0
        if len(regexes) == 1:
            pattern = re.compile(regexes[0], flags)
            base = lambda line: pattern.search(line) is not None
        patterns = [re.compile(r, flags) for r in regexes]
        base = lambda line: any(p.search(line) for p in patterns)
        if and_regexes:
            and_patterns = [re.compile(r, flags) for r in and_regexes]
            return lambda line: base(line) and all(p.search(line) for p in and_patterns)
        return base
    if fixed and keywords:
        needles = [k.lower() if ignore_case else k for k in keywords]
        if ignore_case:
            base = lambda line: any(n in line.lower() for n in needles)
        else:
            base = lambda line: any(n in line for n in needles)
        if and_keywords:
            and_needles = [k.lower() if ignore_case else k for k in and_keywords]
            if ignore_case:
                return lambda line: base(line) and all(n in line.lower() for n in and_needles)
            return lambda line: base(line) and all(n in line for n in and_needles)
        return base
    if ignore_case:
        needles = [k.lower() for k in (keywords or [])]
        base = lambda line: any(n in line.lower() for n in needles)
    needles = list(keywords or [])
    base = lambda line: any(n in line for n in needles)
    if and_keywords:
        and_needles = [k.lower() if ignore_case else k for k in and_keywords]
        if ignore_case:
            return lambda line: base(line) and all(n in line.lower() for n in and_needles)
        return lambda line: base(line) and all(n in line for n in and_needles)
    return base


def _build_highlighter(options: ZGrepOptions) -> Callable[[str], str] | None:
    if options.color not in {"always", "auto"}:
        return None
    flags = re.IGNORECASE if options.ignore_case else 0
    if options.fixed:
        parts = [re.escape(options.pattern)] + [re.escape(p) for p in (options.or_patterns or [])]
        pattern = re.compile("|".join(parts), flags)
    else:
        parts = [options.pattern] + list(options.or_patterns or [])
        pattern = re.compile("|".join(parts), flags)

    def _highlight(text: str) -> str:
        return pattern.sub(lambda m: f"\x1b[01;31m{m.group(0)}\x1b[0m", text)

    return _highlight


def _format_line(
    location: str,
    line_no: int,
    text: str,
    show_filename: bool,
    line_number: bool,
    is_context: bool,
) -> str:
    if line_number:
        if show_filename:
            sep = "-" if is_context else ":"
            return f"{location}{sep}{line_no}{sep}{text}"
        sep = "-" if is_context else ":"
        return f"{line_no}{sep}{text}"
    if show_filename:
        sep = "-" if is_context else ":"
        return f"{location}{sep}{text}"
    return text
