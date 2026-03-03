from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from datetime import datetime
import re
import csv

from .grepper import ZGrepOptions, iter_zgrep_lines


LOG_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<ms>\d{1,6}) (?P<level>\w+) (?P<thread>\S+) (?P<clazz>\S+) (?P<msg>.*)$"
)

TAG_HIT_MAIN = "hit_main"
TAG_HIT_OR = "hit_or"
TAG_HIT_AND = "hit_and"
TAG_ERROR = "level_error"
TAG_WARN = "level_warn"
TAG_INFO = "level_info"
TAG_DEBUG = "level_debug"


class LogxGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("logx")
        self.geometry("1280x900")
        self.minsize(1100, 750)
        self._apply_style()
        self._build_ui()

    def _apply_style(self) -> None:
        self.tk.call("tk", "scaling", 1.35)
        default_font = ("Microsoft YaHei UI", 12)
        self.option_add("*Font", default_font)
        style = ttk.Style(self)
        style.configure("TLabel", padding=(2, 2))
        style.configure("TButton", padding=(8, 6))
        style.configure("TEntry", padding=(4, 4))
        style.configure("TCheckbutton", padding=(4, 4))

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        form = ttk.Frame(main)
        form.pack(fill=tk.X)

        self.path_var = tk.StringVar(value=str(Path("data/workspace").resolve()))
        self.pattern_var = tk.StringVar()
        self.name_var = tk.StringVar(value="collect*")
        self.or_var = tk.StringVar()
        self.and_var = tk.StringVar()
        self.context_var = tk.StringVar(value="0")
        self.max_count_var = tk.StringVar(value="200")
        self.since_var = tk.StringVar()
        self.until_var = tk.StringVar()
        self.level_var = tk.StringVar()
        self.node_var = tk.StringVar()
        self.file_var = tk.StringVar()
        self.highlight_mode_var = tk.StringVar(value="all")
        self.main_color_var = tk.StringVar(value="#d91e18")
        self.or_color_var = tk.StringVar(value="#d98200")
        self.and_color_var = tk.StringVar(value="#1f5aa6")
        self.regex_var = tk.BooleanVar(value=True)
        self.fixed_var = tk.BooleanVar(value=False)
        self.ignore_case_var = tk.BooleanVar(value=False)
        self.line_number_var = tk.BooleanVar(value=True)
        self.include_archives_var = tk.BooleanVar(value=True)
        self.show_advanced_var = tk.BooleanVar(value=False)
        self.show_color_var = tk.BooleanVar(value=True)

        row = 0
        self._add_row(form, row, "Root Path", self.path_var, self._browse_dir)
        row += 1
        self._add_row(form, row, "Pattern", self.pattern_var)
        row += 1
        self._add_row(form, row, "File Name Glob", self.name_var)
        row += 1

        toggles = ttk.Frame(form)
        toggles.grid(row=row, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Checkbutton(
            toggles, text="Advanced Filters", variable=self.show_advanced_var, command=self._toggle_advanced
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(
            toggles, text="Highlight Options", variable=self.show_color_var, command=self._toggle_colors
        ).pack(side=tk.LEFT)
        row += 1

        self.advanced_frame = ttk.Frame(form)
        self.advanced_frame.grid(row=row, column=0, columnspan=3, sticky="we")
        self._build_advanced_rows(self.advanced_frame)
        row += 1

        self.colors_frame = ttk.Frame(form)
        self.colors_frame.grid(row=row, column=0, columnspan=3, sticky="we")
        self._build_color_rows(self.colors_frame)
        row += 1
        self._toggle_advanced()
        self._toggle_colors()

        opts = ttk.Frame(form)
        opts.grid(row=row, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Checkbutton(opts, text="Regex", variable=self.regex_var).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Checkbutton(opts, text="Fixed", variable=self.fixed_var).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Checkbutton(opts, text="Ignore Case", variable=self.ignore_case_var).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Checkbutton(opts, text="Line Number", variable=self.line_number_var).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Checkbutton(opts, text="Include Archives", variable=self.include_archives_var).pack(side=tk.LEFT)
        row += 1

        extra = ttk.Frame(form)
        extra.grid(row=row, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(extra, text="Context").pack(side=tk.LEFT)
        ttk.Entry(extra, textvariable=self.context_var, width=6).pack(side=tk.LEFT, padx=(6, 18))
        ttk.Label(extra, text="Max Matches").pack(side=tk.LEFT)
        ttk.Entry(extra, textvariable=self.max_count_var, width=8).pack(side=tk.LEFT, padx=(6, 18))
        ttk.Button(extra, text="Search", command=self._start_search).pack(side=tk.LEFT)
        ttk.Button(extra, text="Export", command=self._export_results).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(extra, text="Clear", command=self._clear_output).pack(side=tk.LEFT, padx=(6, 0))

        self.output = tk.Text(main, wrap=tk.NONE, font=("Consolas", 13), foreground="#111111", height=18)
        self.output.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self._configure_output_tags()

        yscroll = ttk.Scrollbar(self.output, orient=tk.VERTICAL, command=self.output.yview)
        xscroll = ttk.Scrollbar(self.output, orient=tk.HORIZONTAL, command=self.output.xview)
        self.output.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        xscroll.pack(side=tk.BOTTOM, fill=tk.X)

    def _add_row(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar, browse_cmd=None) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=var, width=96)
        entry.grid(row=row, column=1, sticky="we", padx=8)
        parent.grid_columnconfigure(1, weight=1)
        if browse_cmd:
            ttk.Button(parent, text="Browse", command=browse_cmd).grid(row=row, column=2, padx=(6, 0))

    def _browse_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.path_var.set(path)

    def _build_advanced_rows(self, parent: ttk.Frame) -> None:
        row = 0
        self._add_row(parent, row, "OR Patterns (comma)", self.or_var)
        row += 1
        self._add_row(parent, row, "AND Patterns (comma)", self.and_var)
        row += 1
        self._add_row(parent, row, "Since (YYYY-MM-DD HH:MM:SS)", self.since_var)
        row += 1
        self._add_row(parent, row, "Until (YYYY-MM-DD HH:MM:SS)", self.until_var)
        row += 1
        self._add_row(parent, row, "Level (comma, e.g. ERROR,WARN)", self.level_var)
        row += 1
        self._add_row(parent, row, "Node (comma)", self.node_var)
        row += 1
        self._add_row(parent, row, "File Path Contains", self.file_var)

    def _build_color_rows(self, parent: ttk.Frame) -> None:
        row = 0
        self._add_row(parent, row, "Highlight Mode (main/all)", self.highlight_mode_var)
        row += 1
        self._add_row(parent, row, "Main Color", self.main_color_var)
        row += 1
        self._add_row(parent, row, "OR Color", self.or_color_var)
        row += 1
        self._add_row(parent, row, "AND Color", self.and_color_var)

    def _toggle_advanced(self) -> None:
        if self.show_advanced_var.get():
            self.advanced_frame.grid()
        else:
            self.advanced_frame.grid_remove()

    def _toggle_colors(self) -> None:
        if self.show_color_var.get():
            self.colors_frame.grid()
        else:
            self.colors_frame.grid_remove()

    def _clear_output(self) -> None:
        self.output.delete("1.0", tk.END)
        self._last_results = []

    def _append_output(self, line: str) -> None:
        start = self.output.index("end-1c")
        self.output.insert(tk.END, line + "\n")
        self._apply_highlight(line, start)
        self.output.see(tk.END)

    def _start_search(self) -> None:
        pattern = self.pattern_var.get().strip()
        if not pattern:
            messagebox.showerror("logx", "Pattern is required.")
            return
        try:
            context = max(0, int(self.context_var.get().strip() or "0"))
            max_count = int(self.max_count_var.get().strip() or "0")
        except ValueError:
            messagebox.showerror("logx", "Context/Max Matches must be integers.")
            return

        self._clear_output()
        self._configure_output_tags()
        self._last_results = []

        thread = threading.Thread(
            target=self._run_search,
            args=(pattern, context, max_count),
            daemon=True,
        )
        thread.start()

    def _run_search(self, pattern: str, context: int, max_count: int) -> None:
        root = Path(self.path_var.get().strip() or ".").expanduser().resolve()
        name_glob = self.name_var.get().strip() or "*"
        or_patterns = [p.strip() for p in self.or_var.get().split(",") if p.strip()]
        and_patterns = [p.strip() for p in self.and_var.get().split(",") if p.strip()]
        since = self.since_var.get().strip()
        until = self.until_var.get().strip()
        levels = [p.strip().upper() for p in self.level_var.get().split(",") if p.strip()]
        nodes = [p.strip().lower() for p in self.node_var.get().split(",") if p.strip()]
        file_contains = self.file_var.get().strip()

        if since and not _validate_ts(since):
            self.output.after(0, self._append_output, "Error: invalid 'Since' time format.")
            return
        if until and not _validate_ts(until):
            self.output.after(0, self._append_output, "Error: invalid 'Until' time format.")
            return

        options = ZGrepOptions(
            root=root,
            pattern=pattern,
            or_patterns=or_patterns,
            and_patterns=and_patterns,
            name_glob=name_glob,
            regex=bool(self.regex_var.get()) and not bool(self.fixed_var.get()),
            fixed=bool(self.fixed_var.get()),
            ignore_case=bool(self.ignore_case_var.get()),
            line_number=bool(self.line_number_var.get()),
            context_before=context,
            context_after=context,
            max_count=max_count if max_count > 0 else None,
            files_with_matches=False,
            files_without_match=False,
            count_only=False,
            suppress_filename=False,
            force_filename=False,
            include_archives=bool(self.include_archives_var.get()),
            color="never",
        )

        try:
            count = 0
            for line in iter_zgrep_lines(options):
                if since or until or levels or nodes or file_contains:
                    if not _line_passes_filters(line, since, until, levels, nodes, file_contains):
                        continue
                self.output.after(0, self._append_output, line)
                self._last_results.append(line)
                count += 1
                if max_count > 0 and count >= max_count:
                    break
            if count == 0:
                self.output.after(0, self._append_output, "No results.")
        except Exception as exc:
            self.output.after(0, self._append_output, f"Error: {exc}")

    def _export_results(self) -> None:
        if not getattr(self, "_last_results", None):
            messagebox.showinfo("logx", "No results to export.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Text", "*.txt")],
        )
        if not file_path:
            return
        try:
            if file_path.lower().endswith(".csv"):
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["location", "line_no", "message"])
                    for line in self._last_results:
                        location, line_no, message = _split_line(line)
                        writer.writerow([location, line_no, message])
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    for line in self._last_results:
                        f.write(line + "\n")
            messagebox.showinfo("logx", f"Exported to: {file_path}")
        except Exception as exc:
            messagebox.showerror("logx", f"Export failed: {exc}")

    def _configure_output_tags(self) -> None:
        self.output.tag_configure(TAG_HIT_MAIN, foreground=_safe_color(self.main_color_var.get(), "#d91e18"))
        self.output.tag_configure(TAG_HIT_OR, foreground=_safe_color(self.or_color_var.get(), "#d98200"))
        self.output.tag_configure(TAG_HIT_AND, foreground=_safe_color(self.and_color_var.get(), "#1f5aa6"))
        self.output.tag_configure(TAG_ERROR, foreground="#d91e18")
        self.output.tag_configure(TAG_WARN, foreground="#d98200")
        self.output.tag_configure(TAG_INFO, foreground="#1f5aa6")
        self.output.tag_configure(TAG_DEBUG, foreground="#666666")
        for tag in (TAG_HIT_MAIN, TAG_HIT_OR, TAG_HIT_AND, TAG_ERROR, TAG_WARN, TAG_INFO, TAG_DEBUG):
            self.output.tag_raise(tag)

    def _apply_highlight(self, line: str, start_index: str) -> None:
        # Highlight pattern hits (main + optional OR/AND)
        patterns = [(self.pattern_var.get().strip(), TAG_HIT_MAIN)]
        if self.highlight_mode_var.get().strip().lower() == "all":
            patterns.extend(
                [(p.strip(), TAG_HIT_OR) for p in self.or_var.get().split(",") if p.strip()]
            )
            patterns.extend(
                [(p.strip(), TAG_HIT_AND) for p in self.and_var.get().split(",") if p.strip()]
            )

        for pattern, tag in patterns:
            if not pattern:
                continue
            try:
                fixed = self.fixed_var.get() or not self.regex_var.get()
                if fixed:
                    self._tag_all_occurrences(
                        line, pattern, start_index, tag, ignore_case=self.ignore_case_var.get()
                    )
                else:
                    flags = re.IGNORECASE if self.ignore_case_var.get() else 0
                    for match in re.finditer(pattern, line, flags):
                        self._tag_range(start_index, match.start(), match.end(), tag)
            except re.error:
                continue

        # Highlight by level if present
        level = _extract_level_from_line(line)
        if level == "ERROR":
            self._tag_all_occurrences(line, "ERROR", start_index, TAG_ERROR)
        elif level == "WARN":
            self._tag_all_occurrences(line, "WARN", start_index, TAG_WARN)
        elif level == "INFO":
            self._tag_all_occurrences(line, "INFO", start_index, TAG_INFO)
        elif level == "DEBUG":
            self._tag_all_occurrences(line, "DEBUG", start_index, TAG_DEBUG)

    def _tag_all_occurrences(
        self, line: str, needle: str, start_index: str, tag: str, ignore_case: bool = False
    ) -> None:
        if not needle:
            return
        hay = line.lower() if ignore_case else line
        ndl = needle.lower() if ignore_case else needle
        start = 0
        while True:
            idx = hay.find(ndl, start)
            if idx == -1:
                break
            self._tag_range(start_index, idx, idx + len(needle), tag)
            start = idx + len(needle)

    def _tag_range(self, base_index: str, start: int, end: int, tag: str) -> None:
        start_idx = f"{base_index}+{start}c"
        end_idx = f"{base_index}+{end}c"
        self.output.tag_add(tag, start_idx, end_idx)


def _validate_ts(text: str) -> bool:
    try:
        datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        return True
    except ValueError:
        return False


def _line_passes_filters(
    line: str,
    since: str,
    until: str,
    levels: list[str],
    nodes: list[str],
    file_contains: str,
) -> bool:
    # Expect format: path:line:message
    try:
        _, _, message = line.rsplit(":", 2)
    except ValueError:
        return False

    match = LOG_RE.match(message)
    if not match:
        return False

    ts = match.group("ts")
    level = match.group("level").upper()
    thread = match.group("thread").lower()
    clazz = match.group("clazz")

    if since and ts < since:
        return False
    if until and ts > until:
        return False
    if levels and level not in levels:
        return False
    if nodes:
        hay = f"{thread} {clazz}".lower()
        if not any(n in hay for n in nodes):
            return False
    if file_contains and file_contains not in line:
        return False

    return True


def _safe_color(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if not value:
        return fallback
    return value


def _extract_level_from_line(line: str) -> str | None:
    try:
        _, _, message = line.rsplit(":", 2)
    except ValueError:
        return None
    match = LOG_RE.match(message)
    if not match:
        return None
    return match.group("level").upper()


def _split_line(line: str) -> tuple[str, str, str]:
    try:
        location, line_no, message = line.rsplit(":", 2)
        return location, line_no, message
    except ValueError:
        return "", "", line


def run_gui() -> None:
    app = LogxGui()
    app.mainloop()
