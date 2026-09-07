from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from typing import Callable, Iterable
from urllib.parse import urlparse

from .. import __version__
from ..accessibility import audit_docx_accessibility
from ..api import MarkdownWord
from ..benchmark import run_performance_gate
from ..config import RenderConfig, ResourcePolicy, MetadataConfig
from ..data import load_tabular_data
from ..diagnostics import MddocxError
from ..doctor import run_doctor
from ..inspection import inspect_docx
from ..project import build_project, init_project, load_project, project_info, watch_project, ProjectWatchEvent
from ..styles import THEMES
from ..template_inspection import inspect_template
from ..metadata import sanitize_markdown_metadata
from .history import add_recent, load_recent, repl_history_path
from .fonts import discover_fonts, font_display_name
from .opening import open_path
from .tokenize import split_command
from .workspace import WorkspaceSummary, display_path, inspect_workspace

_MD_REMOTE_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*<?(https://[^)\s>]+)>?", re.IGNORECASE)
_HTML_REMOTE_IMAGE_RE = re.compile(r"<img\b[^>]*\bsrc=[\"\'](https://[^\"\']+)[\"\']", re.IGNORECASE)
_COMMANDS = (
    "menu", "render", "check", "build", "watch", "new", "config", "project",
    "doctor", "inspect", "accessibility", "template", "data", "metadata", "benchmark",
    "recent", "open", "fonts", "diagnostics", "explain", "tools", "cd", "pwd", "files", "help", "clear", "exit", "quit",
)


@dataclass(slots=True)
class ShellResult:
    exit_code: int = 0
    should_exit: bool = False


class InteractiveConsole:
    """Discoverable interactive CLI over the existing mddocx services/API.

    The console owns no renderer/parser logic. It only orchestrates public services.
    """

    def __init__(
        self,
        workspace: str | Path = ".",
        *,
        reader: Callable[[str], str] | None = None,
        writer: Callable[[str], None] | None = None,
        opener: Callable[[str | Path], None] = open_path,
    ) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.reader = reader or input
        self.writer = writer or print
        self.opener = opener
        self.last_output: Path | None = self._discover_last_output()
        self.last_diagnostics: list[str] = []
        self._refresh()

    def _refresh(self) -> None:
        self.summary = inspect_workspace(self.workspace)

    def _discover_last_output(self) -> Path | None:
        for item in load_recent(limit=20):
            path = Path(item.output)
            if path.exists():
                return path
        return None

    @property
    def prompt(self) -> str:
        return f"mddocx [{self.summary.name}]> "

    def println(self, text: str = "") -> None:
        self.writer(text)

    def ask(self, prompt: str, default: str | None = None) -> str:
        suffix = f" [{default}]" if default is not None else ""
        raw = self.reader(f"{prompt}{suffix}: ").strip()
        return raw if raw else (default or "")

    def confirm(self, prompt: str, default: bool = True) -> bool:
        marker = "Y/n" if default else "y/N"
        value = self.reader(f"{prompt} [{marker}] ").strip().lower()
        if not value:
            return default
        return value in {"y", "yes", "1", "true"}

    def choose(self, title: str, options: list[str], default: int = 1) -> int:
        self.println(title)
        for index, option in enumerate(options, start=1):
            self.println(f"  {index}. {option}")
        while True:
            raw = self.ask("Select", str(default))
            try:
                number = int(raw)
            except ValueError:
                self.println("Please enter a number.")
                continue
            if 1 <= number <= len(options):
                return number
            self.println("Selection out of range.")

    def choose_file(self, suffixes: set[str], title: str, *, allow_missing: bool = False) -> Path | None:
        files = self._matching_files(suffixes)
        self.println(title)
        if files:
            for index, path in enumerate(files[:30], start=1):
                self.println(f"  {index:2d}. {display_path(path, self.workspace)}")
            if len(files) > 30:
                self.println(f"  ... {len(files) - 30} more (use Search or Browse path)")
        else:
            self.println("  No matching files discovered in this workspace.")
        self.println("  S. Search")
        self.println("  B. Browse/type path")
        self.println("  Q. Cancel")
        while True:
            raw = self.ask("Select").strip()
            if not raw:
                continue
            lowered = raw.lower()
            if lowered == "q":
                return None
            if lowered == "s":
                query = self.ask("Search filename").casefold()
                matches = [p for p in files if query in str(p.relative_to(self.workspace)).casefold()]
                if not matches:
                    self.println("No matches.")
                    continue
                for i, path in enumerate(matches[:30], start=1):
                    self.println(f"  {i:2d}. {display_path(path, self.workspace)}")
                pick = self.ask("Select match")
                if pick.isdigit() and 1 <= int(pick) <= len(matches[:30]):
                    return matches[int(pick) - 1]
                continue
            if lowered == "b":
                raw = self.ask("Path")
                if not raw:
                    continue
                return self._resolve_path(raw, require_exists=not allow_missing)
            if raw.isdigit() and 1 <= int(raw) <= len(files[:30]):
                return files[int(raw) - 1]
            try:
                return self._resolve_path(raw, require_exists=not allow_missing)
            except OSError as exc:
                self.println(f"ERROR: {exc}")

    def _matching_files(self, suffixes: set[str]) -> list[Path]:
        result: list[Path] = []
        try:
            for path in self.workspace.rglob("*"):
                try:
                    rel_parts = path.relative_to(self.workspace).parts
                except ValueError:
                    continue
                if any(part in {".git", ".mddocx", ".venv", "venv", "node_modules", "__pycache__"} for part in rel_parts[:-1]):
                    continue
                if path.is_file() and path.suffix.lower() in suffixes:
                    result.append(path.resolve())
        except OSError:
            pass
        return sorted(result, key=lambda p: str(p.relative_to(self.workspace)).casefold())

    def _resolve_path(self, raw: str, *, require_exists: bool = True) -> Path:
        value = os.path.expandvars(raw.strip().strip('"').strip("'"))
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.workspace / path
        path = path.resolve()
        if require_exists and not path.exists():
            raise OSError(f"Path does not exist: {path}")
        return path

    def banner(self) -> None:
        self.println("+--------------------------------------------------+")
        self.println(f"|              mddocx {__version__} Console".ljust(51) + "|")
        self.println("|        Markdown -> Native Editable Word          |")
        self.println("+--------------------------------------------------+")
        self.println(f"Workspace: {self.workspace}")
        self.println(f"Project  : {'mddocx.yml' if self.summary.project_file else 'not detected'}")
        self.println(f"Markdown : {len(self.summary.markdown_files)} file(s)")
        self.println(f"DOCX     : {len(self.summary.docx_files)} file(s)")
        self.println(f"Images   : {len(self.summary.image_files)} asset(s)")
        self.println(f"Data     : {len(self.summary.data_files)} CSV/JSON file(s)")
        self.println("")

    def show_menu(self) -> None:
        self.println("What would you like to do?")
        items = [
            "Render Markdown to DOCX",
            "Build a multi-file project",
            "Watch a project",
            "Create a new mddocx project",
            "Configure / inspect this project",
            "Check Markdown without writing DOCX",
            "Inspect a DOCX for structural problems",
            "Run accessibility audit",
            "Template / data tools",
            "Diagnostics / Doctor",
            "Recent documents",
            "Help",
        ]
        for i, item in enumerate(items, start=1):
            self.println(f"  [{i:2d}] {item}")
        self.println("  [ Q] Quit")
        self.println("")
        self.println("Tip: you can also type commands such as `render report.md`, `build`, `doctor`, or `help`.")

    def run(self, *, show_menu: bool = True) -> int:
        self.banner()
        if show_menu:
            self.show_menu()
        while True:
            try:
                line = self.reader(self.prompt)
            except EOFError:
                self.println("")
                return 0
            except KeyboardInterrupt:
                self.println("\nUse `exit` or `quit` to leave the console.")
                continue
            result = self.execute_line(line)
            if result.should_exit:
                return result.exit_code

    def execute_line(self, line: str) -> ShellResult:
        line = line.strip()
        if not line:
            self.show_menu()
            return ShellResult()
        numeric = {
            "1": "render", "2": "build", "3": "watch", "4": "new", "5": "config",
            "6": "check", "7": "inspect", "8": "accessibility", "9": "tools",
            "10": "doctor", "11": "recent", "12": "help",
        }
        if line.lower() in {"q", "quit", "exit"}:
            self.println("Goodbye.")
            return ShellResult(0, True)
        if line in numeric:
            line = numeric[line]
        try:
            tokens = split_command(line)
        except ValueError as exc:
            self.println(f"ERROR: {exc}")
            return ShellResult(2)
        if not tokens:
            return ShellResult()
        command, args = tokens[0].lower(), tokens[1:]
        aliases = {"ls": "files", "dir": "files", "a11y": "accessibility", "new-project": "new", "tools": "tools"}
        command = aliases.get(command, command)
        handlers = {
            "menu": self.cmd_menu,
            "render": self.cmd_render,
            "check": self.cmd_check,
            "build": self.cmd_build,
            "watch": self.cmd_watch,
            "new": self.cmd_new,
            "config": self.cmd_config,
            "project": self.cmd_project,
            "doctor": self.cmd_doctor,
            "inspect": self.cmd_inspect,
            "accessibility": self.cmd_accessibility,
            "template": self.cmd_template,
            "data": self.cmd_data,
            "metadata": self.cmd_metadata,
            "benchmark": self.cmd_benchmark,
            "recent": self.cmd_recent,
            "open": self.cmd_open,
            "fonts": self.cmd_fonts,
            "diagnostics": self.cmd_diagnostics,
            "explain": self.cmd_explain,
            "cd": self.cmd_cd,
            "pwd": self.cmd_pwd,
            "files": self.cmd_files,
            "help": self.cmd_help,
            "clear": self.cmd_clear,
            "tools": self.cmd_tools,
        }
        handler = handlers.get(command)
        if handler is None:
            self.println(f"Unknown command: {command}. Type `help`.")
            return ShellResult(2)
        try:
            code = handler(args)
            return ShellResult(code)
        except KeyboardInterrupt:
            self.println("Cancelled.")
            return ShellResult(130)
        except (MddocxError, OSError, ValueError) as exc:
            if isinstance(exc, MddocxError):
                self.last_diagnostics = [exc.diagnostic.to_dict()]
            self.println(str(exc) if isinstance(exc, MddocxError) else f"ERROR: {exc}")
            return ShellResult(2)

    # ----- commands -------------------------------------------------
    def cmd_menu(self, args: list[str]) -> int:
        self.show_menu(); return 0

    def cmd_render(self, args: list[str]) -> int:
        parser = _nonexiting_parser("render")
        parser.add_argument("source", nargs="?")
        parser.add_argument("-o", "--output")
        parser.add_argument("--theme", choices=sorted(THEMES))
        parser.add_argument("--open", action="store_true")
        parser.add_argument("--allow-remote-resources", action="store_true")
        parser.add_argument("--ai-metadata", choices=["auto", "strip", "keep"], default="auto")
        ns = _parse_interactive(parser, args, self.println)
        if ns is None:
            return 2
        guided = ns.source is None
        source = self._resolve_path(ns.source) if ns.source else self.choose_file({".md", ".markdown", ".mdown", ".mkd"}, "Select a Markdown file:")
        if source is None:
            return 0
        output_default = source.with_suffix(".docx")
        if ns.output:
            output = self._resolve_path(ns.output, require_exists=False)
        elif guided:
            raw_out = self.ask("Output", display_path(output_default, self.workspace))
            output = self._resolve_path(raw_out, require_exists=False)
        else:
            output = output_default
        theme = ns.theme
        if guided and not theme:
            themes = sorted(THEMES)
            theme = themes[self.choose("Theme:", themes, themes.index("default") + 1) - 1]
        theme = theme or "default"
        remote_hosts = _remote_hosts(source)
        allow_remote = bool(ns.allow_remote_resources)
        allowed_domains: tuple[str, ...] | None = None
        if remote_hosts and not allow_remote:
            self.println("Remote resources detected:")
            for host in remote_hosts:
                self.println(f"  - {host}")
            if guided and self.confirm("Allow these HTTPS hosts for this render?", default=False):
                allow_remote = True
                allowed_domains = tuple(remote_hosts)
        elif remote_hosts and allow_remote:
            allowed_domains = tuple(remote_hosts)
        metadata_policy = ns.ai_metadata
        try:
            source_text = source.read_text(encoding="utf-8-sig")
            metadata_preview = sanitize_markdown_metadata(source_text, MetadataConfig(ai_export=metadata_policy))
            if metadata_preview.report.detected_export_metadata:
                if metadata_policy == "keep":
                    self.println("AI/chat export metadata detected; it will be preserved (--ai-metadata keep).")
                else:
                    self.println(
                        f"AI/chat export metadata detected: {metadata_preview.report.removed_lines} line(s), "
                        f"{len(metadata_preview.report.removed_front_matter_keys)} front-matter field(s) will be removed."
                    )
        except OSError:
            pass
        config = RenderConfig(
            theme=theme,
            resources=ResourcePolicy(
                allow_remote_resources=allow_remote,
                allowed_domains=allowed_domains,
            ),
            metadata=MetadataConfig(ai_export=metadata_policy),
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        self.println(f"Rendering {display_path(source, self.workspace)}")
        self.println("  [..] Compiling Markdown into native Word structures")
        converter = MarkdownWord(config)
        started = time.perf_counter()
        converter.render_file(source, output)
        elapsed = time.perf_counter() - started
        report = inspect_docx(output)
        try:
            self.last_diagnostics = json.loads(converter.diagnostics_json())
        except (ValueError, TypeError):
            self.last_diagnostics = []
        size = output.stat().st_size
        self.println("  [OK] DOCX generated")
        self.println(f"  [OK] Equations: {report.equations}  Tables: {report.tables}  Lists: {report.native_list_paragraphs}")
        self.println(f"  [OK] Drawings: {report.drawings}  Charts: {report.native_charts}")
        self.println(f"Completed in {elapsed:.2f} s")
        self.println(f"Output size: {_human_size(size)}")
        self.println(f"Structural issues: {report.structural_issues}  Warnings: {report.quality_warnings}")
        self.println(f"Output: {output}")
        self.last_output = output
        add_recent(source=source, output=output, action="render", workspace=self.workspace, settings={"theme": theme})
        should_open = ns.open or (guided and self.confirm("Open DOCX now?", default=True))
        if should_open:
            self.opener(output)
        self._refresh()
        return 0

    def cmd_check(self, args: list[str]) -> int:
        source = self._resolve_path(args[0]) if args else self.choose_file({".md", ".markdown", ".mdown", ".mkd"}, "Select Markdown to check:")
        if source is None:
            return 0
        converter = MarkdownWord(RenderConfig())
        converter.check_file(source)
        self.println(f"OK {source}")
        return 0

    def cmd_build(self, args: list[str]) -> int:
        force = "--force" in args
        open_after = "--open" in args
        raw_project = next((x for x in args if not x.startswith("-")), None)
        project = self._resolve_path(raw_project) if raw_project else (self.summary.project_file or self.workspace)
        self.println(f"Building project: {project}")
        result = build_project(project, force=force)
        status = "BUILT" if result.built else "UP-TO-DATE"
        self.println(f"{status} {result.output_path}")
        self.println(f"Dependencies: {len(result.dependencies)}")
        self.println(f"Completed in {result.elapsed_ms / 1000:.2f} s")
        self.last_output = result.output_path
        add_recent(source=result.project_file, output=result.output_path, action="build", workspace=self.workspace, settings={"fingerprint": result.fingerprint})
        if open_after:
            self.opener(result.output_path)
        self._refresh()
        return 0

    def cmd_watch(self, args: list[str]) -> int:
        once = "--once" in args
        raw_project = next((x for x in args if not x.startswith("-")), None)
        project = self._resolve_path(raw_project) if raw_project else (self.summary.project_file or self.workspace)
        manifest = load_project(project)
        self.println(f"Watching: {manifest.root}")
        self.println(f"Output  : {manifest.output}")
        self.println("Press Ctrl+C to stop.")

        def on_event(event: ProjectWatchEvent) -> None:
            stamp = datetime.now().strftime("%H:%M:%S")
            if event.kind == "change":
                names = ", ".join(display_path(p, manifest.root) for p in event.changed[:6])
                self.println(f"{stamp} CHANGE {names}")
            elif event.kind == "build" and event.result is not None:
                status = "rebuilt" if event.result.built else "up-to-date"
                self.println(f"{stamp} [OK] {status} in {event.result.elapsed_ms / 1000:.2f}s")
                self.last_output = event.result.output_path
            elif event.kind == "error":
                self.println(f"{stamp} ERROR {event.error}")

        try:
            watch_project(manifest, once=once, on_event=on_event)
        except KeyboardInterrupt:
            self.println("Watch stopped.")
        return 0

    def cmd_new(self, args: list[str]) -> int:
        directory = args[0] if args else self.ask("Project directory", "my-document")
        root = self._resolve_path(directory, require_exists=False)
        path = init_project(root)
        title = self.ask("Document title", "My Document")
        theme = sorted(THEMES)[self.choose("Theme:", sorted(THEMES), sorted(THEMES).index("default") + 1) - 1]
        _update_project_yaml(path, {"variables.project_name": title, "render.title": title, "render.theme": theme})
        self.println(f"Created project: {path}")
        if self.confirm("Switch workspace to the new project?", default=True):
            self.workspace = root
            self._refresh()
        return 0

    def cmd_config(self, args: list[str]) -> int:
        if not self.summary.project_file:
            self.println("No mddocx.yml found in this workspace.")
            return 2
        path = self.summary.project_file
        if args and args[0] == "show":
            self.println(path.read_text(encoding="utf-8")); return 0
        if len(args) >= 3 and args[0] == "set":
            key = args[1]
            value = _coerce_scalar(" ".join(args[2:]))
            _update_project_yaml(path, {key: value})
            self.println(f"Updated {key} = {value!r}")
            self._refresh(); return 0
        self._show_project_config(path)
        if not self.confirm("Change a common setting?", default=False):
            return 0
        choices = ["Theme", "Title", "Table of contents", "Heading numbering", "Equation numbering", "Caption numbering", "Page X of Y", "AI export metadata", "Output path"]
        pick = self.choose("Project configuration", choices)
        if pick == 1:
            themes = sorted(THEMES); value = themes[self.choose("Theme", themes) - 1]; changes = {"render.theme": value}
        elif pick == 2:
            changes = {"render.title": self.ask("Title")}
        elif pick == 3:
            changes = {"render.toc": self.confirm("Enable TOC?", True)}
        elif pick == 4:
            changes = {"render.heading_numbering": self.confirm("Enable heading numbering?", True)}
        elif pick == 5:
            value = ["document", "section"][self.choose("Equation numbering", ["Document", "Section/chapter"]) - 1]; changes = {"render.equation_numbering": value}
        elif pick == 6:
            value = ["document", "section"][self.choose("Caption numbering", ["Document", "Section/chapter"]) - 1]; changes = {"render.caption_numbering": value}
        elif pick == 7:
            changes = {"render.page_x_of_y": self.confirm("Enable Page X of Y?", True)}
        elif pick == 8:
            values = ["auto", "strip", "keep"]
            changes = {"render.ai_metadata": values[self.choose("AI export metadata", ["Auto-strip high-confidence metadata", "Force strip recognized metadata", "Keep export metadata"]) - 1]}
        else:
            changes = {"output": self.ask("Output path", "build/document.docx")}
        _update_project_yaml(path, changes)
        self.println("Configuration updated.")
        self._refresh()
        return 0

    def _show_project_config(self, path: Path) -> None:
        import yaml
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        render = loaded.get("render") or {}
        self.println("Project configuration")
        self.println(f"  Output ............... {loaded.get('output', 'build/document.docx')}")
        self.println(f"  Theme ................ {render.get('theme', 'default')}")
        self.println(f"  Title ................ {render.get('title', '(not set)')}")
        self.println(f"  TOC .................. {'enabled' if render.get('toc') else 'disabled'}")
        self.println(f"  Heading numbering .... {'enabled' if render.get('heading_numbering') else 'disabled'}")
        self.println(f"  Equation numbering ... {render.get('equation_numbering', 'document')}")
        self.println(f"  Caption numbering .... {render.get('caption_numbering', 'document')}")
        self.println(f"  Page X of Y .......... {'enabled' if render.get('page_x_of_y') else 'disabled'}")
        self.println(f"  AI export metadata ... {render.get('ai_metadata', 'auto')}")

    def cmd_project(self, args: list[str]) -> int:
        if args and args[0] == "init":
            return self.cmd_new(args[1:])
        info = project_info(self.summary.project_file or self.workspace)
        self.println(f"Manifest: {info['manifest']}")
        self.println(f"Output: {info['output']}")
        self.println(f"Sources: {info['source_count']}  Includes: {info['include_count']}")
        self.println("Dependencies:")
        for dep in info["dependencies"][:30]:
            self.println(f"  {dep}")
        return 0

    def cmd_doctor(self, args: list[str]) -> int:
        report = run_doctor()
        self.println(report.to_text())
        if self.summary.project_file:
            try:
                info = project_info(self.summary.project_file)
                self.println("\nWorkspace")
                self.println(f"  Project ............... ready")
                self.println(f"  Sources ............... {info['source_count']}")
                self.println(f"  Includes .............. {info['include_count']}")
                self.println(f"  Dependencies .......... {len(info['dependencies'])}")
            except Exception as exc:
                self.println(f"  Project ............... warning: {exc}")
        return 0 if report.ok else 2

    def cmd_inspect(self, args: list[str]) -> int:
        target = self._pick_docx(args)
        if target is None: return 0
        report = inspect_docx(target)
        self.println(report.to_text())
        return 0 if report.ok else 2

    def cmd_accessibility(self, args: list[str]) -> int:
        target = self._pick_docx(args)
        if target is None: return 0
        report = audit_docx_accessibility(target)
        self.println(report.to_text())
        return 0 if report.passes("medium") else 2

    def _pick_docx(self, args: list[str]) -> Path | None:
        if args:
            return self._resolve_path(args[0])
        if self.last_output and self.last_output.exists() and self.confirm(f"Use last output {self.last_output.name}?", default=True):
            return self.last_output
        return self.choose_file({".docx"}, "Select a DOCX:")

    def cmd_template(self, args: list[str]) -> int:
        if args and args[0] == "inspect": args = args[1:]
        target = self._resolve_path(args[0]) if args else self.choose_file({".docx", ".dotx"}, "Select a Word template/document:")
        if target is None: return 0
        self.println(inspect_template(target).to_text())
        return 0

    def cmd_data(self, args: list[str]) -> int:
        if args and args[0] == "inspect": args = args[1:]
        target = self._resolve_path(args[0]) if args else self.choose_file({".csv", ".json"}, "Select CSV/JSON data:")
        if target is None: return 0
        data = load_tabular_data(target)
        self.println(f"Data source: {target}")
        self.println(f"Rows: {len(data.rows)}")
        self.println(f"Columns ({len(data.columns)}): {', '.join(data.columns)}")
        return 0

    def cmd_metadata(self, args: list[str]) -> int:
        policy = "auto"
        if "--keep" in args:
            policy = "keep"
        elif "--strip" in args:
            policy = "strip"
        raw_source = next((x for x in args if not x.startswith("-")), None)
        source = self._resolve_path(raw_source) if raw_source else self.choose_file({".md", ".markdown", ".mdown", ".mkd"}, "Select Markdown to inspect for AI/export metadata:")
        if source is None:
            return 0
        result = sanitize_markdown_metadata(source.read_text(encoding="utf-8-sig"), MetadataConfig(ai_export=policy))
        r = result.report
        self.println(f"AI/export metadata detected: {'yes' if r.detected_export_metadata else 'no'}")
        self.println(f"Policy: {r.policy}")
        self.println(f"Would remove: {r.removed_lines} source line(s), {len(r.removed_front_matter_keys)} front-matter field(s)")
        if r.removed_front_matter_keys:
            self.println("Fields: " + ", ".join(r.removed_front_matter_keys))
        for reason in r.reasons:
            self.println(f"  - {reason}")
        return 0

    def cmd_benchmark(self, args: list[str]) -> int:
        sections = 100
        if args and args[0].isdigit(): sections = max(1, int(args[0]))
        report = run_performance_gate(sections=sections, max_seconds=30.0, max_peak_memory_bytes=512 * 1024 * 1024)
        self.println(report.to_text())
        return 0 if report.ok else 2

    def cmd_recent(self, args: list[str]) -> int:
        items = load_recent(limit=20)
        if not items:
            self.println("No recent renders/builds recorded yet."); return 0
        self.println("Recently generated documents")
        for i, item in enumerate(items, start=1):
            output = Path(item.output)
            self.println(f"  {i:2d}. {Path(item.source).name} -> {output.name}")
            self.println(f"      {item.created_at}  [{item.action}]")
        if args and args[0].isdigit():
            index = int(args[0])
            if 1 <= index <= len(items):
                self.last_output = Path(items[index - 1].output)
        return 0

    def cmd_fonts(self, args: list[str]) -> int:
        fonts = discover_fonts()
        if not fonts:
            self.println("No system font files were discovered in standard font directories.")
            return 0
        query = " ".join(args).casefold().strip()
        if query:
            fonts = tuple(p for p in fonts if query in p.name.casefold() or query in font_display_name(p).casefold())
        self.println(f"System fonts: {len(fonts)} matching file(s)")
        for path in fonts[:50]:
            self.println(f"  {font_display_name(path)}  [{path.name}]")
        if len(fonts) > 50:
            self.println(f"  ... {len(fonts) - 50} more. Use `fonts SEARCH` to narrow the list.")
        return 0

    def cmd_diagnostics(self, args: list[str]) -> int:
        if not self.last_diagnostics:
            self.println("No diagnostics are recorded in this shell session yet.")
            self.println("Run `render` or `check`; failures and warnings will appear here.")
            return 0
        self.println("Recent diagnostics")
        for index, item in enumerate(self.last_diagnostics, start=1):
            if isinstance(item, dict):
                code = item.get("code", "UNKNOWN")
                severity = str(item.get("severity", "info")).upper()
                message = item.get("message", "")
                location = item.get("source_file") or ""
                if item.get("line") is not None:
                    location = f"{location}:{item.get('line')}"
                self.println(f"  {index}. {severity} {code} {message}" + (f" [{location}]" if location else ""))
        return 0

    def cmd_explain(self, args: list[str]) -> int:
        code = args[0].upper() if args else ""
        if not code and self.last_diagnostics:
            first = self.last_diagnostics[0]
            if isinstance(first, dict):
                code = str(first.get("code", "")).upper()
        if not code:
            self.println("Usage: explain CODE (for example: explain RESOURCE201)")
            return 2
        exact = {
            "RESOURCE201": "Remote resources are disabled. Keep the resource local, or explicitly allow HTTPS resources for that render. The interactive render wizard can allow only the detected hosts.",
            "RESOURCE203": "A local resource path escaped the Markdown/project root. Move the asset inside the allowed root and use a relative path.",
            "RESOURCE209": "The remote host is not in the explicit allow-list for this render.",
            "RESOURCE211": "Private, loopback, link-local and other non-global network targets are blocked even when remote resources are enabled.",
            "IMAGE208": "SVG support needs the image extra/CairoSVG runtime. Install mddocx with its image dependencies.",
            "DATA201": "A referenced CSV/JSON data source was not found.",
            "PROJECT805": "A recursive @include cycle was detected. Remove or restructure the include loop.",
            "META101": "AI/chat export metadata was detected and removed before Markdown parsing. Use `metadata FILE.md` to inspect it or render with `--ai-metadata keep` when the provenance is intentional.",
            "META102": "AI/chat export metadata was detected but preserved because the metadata policy is `keep`.",
        }
        prefix = {
            "RESOURCE": "Resource-policy diagnostic. Check local paths, HTTPS policy, host allow-lists, file-size limits and network safety rules.",
            "IMAGE": "Image diagnostic. Check format support, validity, conversion dependencies and safe SVG restrictions.",
            "PROJECT": "Project-build diagnostic. Check mddocx.yml, source/include paths, variables and dependency cycles.",
            "DATA": "Structured-data diagnostic. Check CSV/JSON format, columns and configured row/column limits.",
            "MATH": "Equation diagnostic. Check the LaTeX expression and supported native Word-math constructs.",
            "TABLE": "Table diagnostic. Check width/layout constraints and table content.",
            "PLUGIN": "Extension/plugin loading diagnostic. Check the explicit plugin name and installed entry points.",
            "META": "Metadata-sanitization diagnostic. Inspect the Markdown with `mddocx metadata inspect` and choose auto, strip, or keep explicitly when needed.",
        }
        message = exact.get(code)
        if message is None:
            message = next((text for key, text in prefix.items() if code.startswith(key)), "No built-in explanation is available for this code yet. The original diagnostic message remains authoritative.")
        self.println(code)
        self.println(message)
        return 0

    def cmd_open(self, args: list[str]) -> int:
        if args:
            target = self._resolve_path(args[0])
        elif self.last_output is not None:
            target = self.last_output
        else:
            recent = load_recent(limit=1)
            if not recent:
                self.println("No recent output is available."); return 2
            target = Path(recent[0].output)
        self.opener(target)
        self.println(f"Opened: {target}")
        return 0

    def cmd_cd(self, args: list[str]) -> int:
        if not args:
            self.println(str(self.workspace)); return 0
        target = self._resolve_path(args[0])
        if not target.is_dir(): raise OSError(f"Not a directory: {target}")
        self.workspace = target
        self._refresh()
        self.println(f"Workspace: {self.workspace}")
        return 0

    def cmd_pwd(self, args: list[str]) -> int:
        self.println(str(self.workspace)); return 0

    def cmd_files(self, args: list[str]) -> int:
        self._refresh()
        self.println("Workspace files")
        self.println(f"  Markdown .............. {len(self.summary.markdown_files)}")
        for path in self.summary.markdown_files[:20]: self.println(f"    {display_path(path, self.workspace)}")
        self.println(f"  DOCX .................. {len(self.summary.docx_files)}")
        self.println(f"  Images ................ {len(self.summary.image_files)}")
        self.println(f"  Data .................. {len(self.summary.data_files)}")
        return 0

    def cmd_tools(self, args: list[str]) -> int:
        pick = self.choose("Template / data / metadata / font tools", ["Inspect Word template", "Inspect CSV/JSON data", "Inspect AI/chat export metadata", "Browse system fonts", "Run benchmark", "Back"])
        if pick == 1: return self.cmd_template([])
        if pick == 2: return self.cmd_data([])
        if pick == 3: return self.cmd_metadata([])
        if pick == 4: return self.cmd_fonts([])
        if pick == 5: return self.cmd_benchmark([])
        return 0

    def cmd_help(self, args: list[str]) -> int:
        topic = args[0].lower() if args else None
        if topic:
            details = {
                "render": "render [FILE.md] [-o OUTPUT.docx] [--theme THEME] [--open] [--allow-remote-resources] [--ai-metadata auto|strip|keep]",
                "build": "build [PROJECT] [--force] [--open]",
                "watch": "watch [PROJECT] [--once]",
                "check": "check [FILE.md]",
                "config": "config | config show | config set dotted.key VALUE",
                "project": "project | project init [DIRECTORY]",
                "inspect": "inspect [FILE.docx]",
                "accessibility": "accessibility [FILE.docx]",
                "template": "template [inspect] [FILE.docx|FILE.dotx]",
                "data": "data [inspect] [FILE.csv|FILE.json]",
                "metadata": "metadata [FILE.md] [--strip|--keep]",
                "recent": "recent [NUMBER]",
                "open": "open [FILE.docx]",
            }
            self.println(details.get(topic, f"No detailed help for {topic}.")); return 0
        self.println("DOCUMENTS")
        self.println("  render       Guided or direct Markdown -> DOCX")
        self.println("  check        Parse/validate Markdown without writing")
        self.println("  inspect      Inspect generated DOCX structure")
        self.println("  accessibility Audit Word accessibility")
        self.println("  open         Open the last/result DOCX")
        self.println("PROJECT")
        self.println("  build        Build mddocx.yml project")
        self.println("  watch        Watch and rebuild project")
        self.println("  new          Create starter project")
        self.println("  config       View/edit common project settings")
        self.println("  project      Show project dependency information")
        self.println("TOOLS")
        self.println("  doctor       Runtime/workspace diagnostics")
        self.println("  template     Inspect Word templates")
        self.println("  data         Inspect CSV/JSON chart/table data")
        self.println("  metadata     Inspect AI/chat export metadata before conversion")
        self.println("  fonts        Browse/search standard system fonts")
        self.println("  diagnostics  Show warnings/errors from this shell session")
        self.println("  explain      Explain common diagnostic codes")
        self.println("  benchmark    Run performance gate")
        self.println("SHELL")
        self.println("  cd / pwd / files / recent / clear / menu / exit")
        self.println("Type `help COMMAND` for syntax.")
        return 0

    def cmd_clear(self, args: list[str]) -> int:
        # ANSI clear works in modern Windows Terminal/PowerShell/Command Prompt and Unix terminals.
        self.writer("\033[2J\033[H")
        return 0


def _remote_hosts(source: Path) -> list[str]:
    try:
        text = source.read_text(encoding="utf-8-sig")
    except OSError:
        return []
    hosts: set[str] = set()
    urls = [m.group(1) for m in _MD_REMOTE_IMAGE_RE.finditer(text)]
    urls.extend(m.group(1) for m in _HTML_REMOTE_IMAGE_RE.finditer(text))
    for url in urls:
        host = urlparse(url).hostname
        if host:
            hosts.add(host.lower())
    return sorted(hosts)


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def _nonexiting_parser(prog: str) -> argparse.ArgumentParser:
    return argparse.ArgumentParser(prog=f"mddocx shell {prog}", add_help=False, exit_on_error=False)


def _parse_interactive(parser: argparse.ArgumentParser, args: list[str], writer: Callable[[str], None]):
    try:
        return parser.parse_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        writer(f"Invalid command options: {exc}")
        return None


def _coerce_scalar(value: str):
    lowered = value.strip().lower()
    if lowered in {"true", "yes", "on"}: return True
    if lowered in {"false", "no", "off"}: return False
    if lowered in {"null", "none", "~"}: return None
    try: return int(value)
    except ValueError: pass
    try: return float(value)
    except ValueError: return value


def _update_project_yaml(path: Path, changes: dict[str, object]) -> None:
    import yaml
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict): raise ValueError("Project YAML must be a mapping")
    for dotted, value in changes.items():
        parts = dotted.split(".")
        current = loaded
        for part in parts[:-1]:
            child = current.get(part)
            if not isinstance(child, dict):
                child = {}; current[part] = child
            current = child
        current[parts[-1]] = value
    path.write_text(yaml.safe_dump(loaded, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _make_prompt_reader(workspace_getter: Callable[[], Path]):
    if not sys.stdin.isatty():
        return input
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.history import FileHistory
    except ImportError:
        return input

    history_path = repl_history_path()
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history = FileHistory(str(history_path))
    except OSError:
        history = None

    class ShellCompleter(Completer):
        def get_completions(self, document, complete_event):
            before = document.text_before_cursor
            stripped = before.lstrip()
            if not stripped or " " not in stripped:
                word = document.get_word_before_cursor().lower()
                for command in _COMMANDS:
                    if command.startswith(word):
                        yield Completion(command, start_position=-len(word))
                return
            command = stripped.split(None, 1)[0].lower()
            if command in {"render", "check", "cd", "inspect", "accessibility", "template", "data", "open", "build", "watch"}:
                fragment = before.rsplit(" ", 1)[-1]
                quote = fragment[:1] if fragment[:1] in {"\"", "'"} else ""
                raw_fragment = fragment[1:] if quote else fragment
                candidate = Path(raw_fragment).expanduser()
                if candidate.is_absolute():
                    parent = candidate.parent
                    prefix = candidate.name
                else:
                    parent = workspace_getter() / candidate.parent
                    prefix = candidate.name
                try:
                    children = sorted(parent.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))
                except OSError:
                    children = []
                for child in children:
                    if not child.name.casefold().startswith(prefix.casefold()):
                        continue
                    replacement = child.name + (os.sep if child.is_dir() else "")
                    yield Completion(replacement, start_position=-len(prefix), display=replacement)

    session = PromptSession(history=history, completer=ShellCompleter(), complete_while_typing=False)
    return session.prompt


def run_shell(workspace: str | Path = ".", *, show_menu: bool = True) -> int:
    console: InteractiveConsole
    # PromptSession is created after console so its workspace can change during the session.
    console = InteractiveConsole(workspace)
    reader = _make_prompt_reader(lambda: console.workspace)
    console.reader = reader
    return console.run(show_menu=show_menu)
