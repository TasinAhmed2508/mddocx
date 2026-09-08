from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import __version__
from .api import MarkdownWord
from .batch import collect_markdown_inputs, render_many
from .config import (
    CacheConfig,
    CompilationLimits,
    FontConfig,
    FooterConfig,
    HeaderConfig,
    MermaidConfig,
    PageConfig,
    PerformanceConfig,
    PluginConfig,
    RenderConfig,
    ReproducibilityConfig,
    ResourcePolicy,
    TableConfig,
    TOCConfig,
    ValidationConfig,
    NotesConfig,
    CitationConfig,
    ReferenceConfig,
    HeadingNumberingConfig,
    TitlePageConfig,
    AbstractConfig,
    CodeConfig,
    CommentConfig,
    MetadataConfig,
    MathFailurePolicy,
)
from .diagnostics import MddocxError
from .data import load_tabular_data
from .styles import THEMES
from .inspection import inspect_docx
from .doctor import run_doctor
from .accessibility import audit_docx_accessibility
from .benchmark import run_performance_gate
from .api_stability import get_public_api_manifest
from .template_inspection import inspect_template
from .project import (
    build_project,
    compile_project,
    init_project,
    load_project,
    project_info,
    watch_project,
    ProjectWatchEvent,
)
from .visual_qa import (
    VisualQAUnavailable,
    compare_visual_pages,
    render_docx_pages,
    update_visual_baseline,
)
from .interactive import run_shell
from .interactive.history import add_recent, load_recent
from .interactive.opening import open_path
from .metadata import sanitize_markdown_metadata
from .math.preflight import inspect_math_file


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mddocx",
        description="Compile Markdown into native editable Microsoft Word DOCX.",
        epilog="Interactive: mddocx shell | Project: mddocx build/watch/project | QA: mddocx inspect/doctor/accessibility",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("input", nargs="+", type=Path)
    p.add_argument("-o", "--output", type=Path)
    p.add_argument(
        "--output-dir", type=Path, help="Batch output directory; enables multi-input conversion"
    )
    p.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively include .md files from input directories",
    )
    p.add_argument(
        "--fail-fast", action="store_true", help="Stop batch conversion after the first failure"
    )
    p.add_argument("--check", action="store_true", help="Parse and validate without writing DOCX")
    p.add_argument("--theme", choices=sorted(THEMES), default="default")
    p.add_argument(
        "--template", type=Path, help="Use an existing DOCX/DOTX as the document template"
    )
    p.add_argument("--page-size", choices=["A4", "Letter"], default="A4")
    p.add_argument("--orientation", choices=["portrait", "landscape"], default="portrait")
    p.add_argument("--override-template-page-setup", action="store_true")
    p.add_argument("--title")
    p.add_argument("--author")
    p.add_argument("--title-page", action="store_true", help="Generate a professional title page")
    p.add_argument("--subtitle")
    p.add_argument("--organization")
    p.add_argument("--abstract", dest="abstract_text")
    p.add_argument(
        "--keyword", action="append", default=[], help="Document keyword; may be repeated"
    )
    p.add_argument(
        "--heading-numbering",
        action="store_true",
        help="Use native multilevel numbering for headings",
    )
    p.add_argument("--heading-numbering-depth", type=int, default=3)
    p.add_argument("--equation-numbering", choices=["document", "section"], default="document")
    p.add_argument("--caption-numbering", choices=["document", "section"], default="document")
    p.add_argument("--toc", action="store_true", help="Insert a native Word TOC field")
    p.add_argument("--page-numbers", action="store_true", help="Insert PAGE field in the footer")
    p.add_argument("--num-pages", action="store_true", help="Insert NUMPAGES field in the footer")
    p.add_argument("--page-x-of-y", action="store_true", help="Render Page X of Y in the footer")
    p.add_argument(
        "--different-first-page",
        action="store_true",
        help="Enable separate first-page header/footer",
    )
    p.add_argument(
        "--different-odd-even", action="store_true", help="Enable separate even-page header/footer"
    )
    p.add_argument("--first-header", help="First-page header field template")
    p.add_argument("--even-header", help="Even-page header field template")
    p.add_argument("--first-footer", help="First-page footer field template")
    p.add_argument("--even-footer", help="Even-page footer field template")
    p.add_argument(
        "--notes",
        choices=["footnote", "endnote"],
        default="footnote",
        help="Render Markdown notes as native Word footnotes or endnotes",
    )
    p.add_argument("--bibliography", type=Path, help="BibTeX or CSL-JSON bibliography file")
    p.add_argument(
        "--citation-style", choices=["author-year", "apa", "ieee", "numeric"], default="author-year"
    )
    p.add_argument(
        "--auto-bibliography",
        action="store_true",
        help="Append a bibliography when citations are present",
    )
    p.add_argument(
        "--no-crossrefs",
        action="store_true",
        help="Disable numbered caption/cross-reference features",
    )
    p.add_argument("--header", help="Header text")
    p.add_argument("--footer", help="Footer text")
    p.add_argument("--font", help="Body font")
    p.add_argument("--heading-font", help="Heading font")
    p.add_argument("--code-font", help="Code font")
    p.add_argument(
        "--code-line-numbers", action="store_true", help="Add editable line numbers to code blocks"
    )
    p.add_argument("--code-language-labels", action="store_true", help="Show code-language labels")
    p.add_argument(
        "--no-syntax-highlighting",
        action="store_true",
        help="Disable editable Pygments token highlighting",
    )
    p.add_argument(
        "--comment-author", default="mddocx", help="Author for CriticMarkup native Word comments"
    )
    p.add_argument("--comment-initials", default="MD", help="Initials for native Word comments")
    p.add_argument("--east-asia-font", help="East Asian script font")
    p.add_argument("--complex-script-font", help="Arabic/Hebrew complex-script font")
    p.add_argument("--rtl", choices=["off", "auto", "force"], default="auto")
    p.add_argument(
        "--auto-landscape-tables",
        action="store_true",
        help="Place wide tables in landscape sections",
    )
    p.add_argument(
        "--no-mermaid",
        action="store_true",
        help="Keep Mermaid fences as editable code instead of rendering supported diagrams",
    )
    p.add_argument(
        "--mermaid-strict",
        action="store_true",
        help="Fail instead of falling back to code for unsupported Mermaid syntax",
    )
    p.add_argument(
        "--strict-math",
        action="store_true",
        help="Fail conversion when an equation cannot be rendered as native Word math",
    )
    p.add_argument(
        "--allow-remote-resources", action="store_true", help="Allow safe HTTPS image downloads"
    )
    p.add_argument(
        "--allow-domain",
        action="append",
        default=[],
        help="Restrict remote image hosts; may be repeated",
    )
    p.add_argument(
        "--plugin",
        action="append",
        default=[],
        metavar="NAME",
        help="Load an explicitly named mddocx.extensions entry point",
    )
    p.add_argument(
        "--ast-cache",
        nargs="?",
        const=".mddocx-cache",
        metavar="DIR",
        help="Enable persistent normalized-AST cache",
    )
    p.add_argument("--max-input-bytes", type=int, default=20_000_000)
    p.add_argument(
        "--no-reproducible", action="store_true", help="Do not normalize DOCX ZIP metadata/order"
    )
    p.add_argument(
        "--no-validate-output", action="store_true", help="Skip generated DOCX package validation"
    )
    p.add_argument(
        "--diagnostics-json",
        nargs="?",
        const="-",
        metavar="PATH",
        help="Write diagnostics JSON (default: stdout)",
    )
    p.add_argument(
        "--diagnostics-sarif",
        nargs="?",
        const="-",
        metavar="PATH",
        help="Write SARIF 2.1.0 diagnostics (default: stdout)",
    )
    p.add_argument(
        "--profile",
        action="store_true",
        help="Print render timing, hash, cache and memory statistics as JSON",
    )
    p.add_argument(
        "--profile-memory", action="store_true", help="Track peak Python allocation memory"
    )
    p.add_argument(
        "--ai-metadata",
        choices=["auto", "strip", "keep"],
        default="auto",
        help="AI/chat export metadata handling: auto-strip high-confidence metadata (default), force strip, or keep",
    )
    p.add_argument(
        "--open",
        action="store_true",
        help="Open the generated DOCX with the operating-system default application",
    )
    return p


def _write_text_target(target: str | None, text: str) -> None:
    if not target:
        return
    if target == "-":
        print(text)
    else:
        Path(target).write_text(text + "\n", encoding="utf-8")


def _config_from_args(args: argparse.Namespace) -> RenderConfig:
    return RenderConfig(
        theme=args.theme,
        template=args.template,
        preserve_template_page_setup=not args.override_template_page_setup,
        page=PageConfig(size=args.page_size, orientation=args.orientation),
        title=args.title,
        author=args.author,
        title_page=TitlePageConfig(
            enabled=args.title_page or bool(args.subtitle) or bool(args.organization),
            subtitle=args.subtitle,
            organization=args.organization,
        ),
        abstract=AbstractConfig(text=args.abstract_text, keywords=tuple(args.keyword)),
        heading_numbering=HeadingNumberingConfig(
            enabled=args.heading_numbering, max_level=max(1, min(6, args.heading_numbering_depth))
        ),
        toc=TOCConfig(enabled=args.toc),
        header=HeaderConfig(
            enabled=bool(args.header) or bool(args.first_header) or bool(args.even_header),
            text=args.header,
            different_first_page=args.different_first_page,
            different_odd_even=args.different_odd_even,
            first_page_text=args.first_header,
            even_page_text=args.even_header,
        ),
        footer=FooterConfig(
            enabled=bool(args.footer)
            or args.page_numbers
            or args.num_pages
            or args.page_x_of_y
            or bool(args.first_footer)
            or bool(args.even_footer),
            text=args.footer,
            page_number=args.page_numbers,
            num_pages=args.num_pages,
            page_x_of_y=args.page_x_of_y,
            different_first_page=args.different_first_page,
            different_odd_even=args.different_odd_even,
            first_page_text=args.first_footer,
            even_page_text=args.even_footer,
        ),
        code=CodeConfig(
            syntax_highlighting=not args.no_syntax_highlighting,
            line_numbers=args.code_line_numbers,
            show_language_label=args.code_language_labels,
        ),
        native_comments=CommentConfig(author=args.comment_author, initials=args.comment_initials),
        fonts=FontConfig(
            body=args.font,
            headings=args.heading_font,
            code=args.code_font,
            east_asia=args.east_asia_font,
            complex_script=args.complex_script_font,
        ),
        rtl=args.rtl,
        table=TableConfig(auto_landscape=args.auto_landscape_tables),
        mermaid=MermaidConfig(
            enabled=not args.no_mermaid, fallback="error" if args.mermaid_strict else "code"
        ),
        math_failure=MathFailurePolicy(mode="error" if args.strict_math else "warning"),
        resources=ResourcePolicy(
            allow_remote_resources=args.allow_remote_resources,
            allowed_domains=tuple(args.allow_domain) or None,
        ),
        metadata=MetadataConfig(ai_export=args.ai_metadata),
        performance=PerformanceConfig(
            enabled=args.profile or args.profile_memory, track_memory=args.profile_memory
        ),
        limits=CompilationLimits(max_input_bytes=args.max_input_bytes),
        reproducibility=ReproducibilityConfig(enabled=not args.no_reproducible),
        validation=ValidationConfig(validate_output=not args.no_validate_output),
        cache=CacheConfig(
            ast_enabled=bool(args.ast_cache),
            directory=Path(args.ast_cache) if args.ast_cache else None,
        ),
        plugins=PluginConfig(names=tuple(args.plugin)),
        notes=NotesConfig(style=args.notes),
        citations=CitationConfig(
            bibliography=args.bibliography,
            style=args.citation_style,
            auto_bibliography=args.auto_bibliography,
        ),
        references=ReferenceConfig(
            enabled=not args.no_crossrefs,
            captions=not args.no_crossrefs,
            equation_number_format=args.equation_numbering,
            caption_number_format=args.caption_numbering,
        ),
    )


def _main_inspect(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="mddocx inspect",
        description="Inspect DOCX structure for common rendering/package defects.",
    )
    p.add_argument("docx", type=Path)
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p.add_argument(
        "--strict", action="store_true", help="Return exit code 2 when structural issues are found"
    )
    args = p.parse_args(argv)
    try:
        report = inspect_docx(args.docx)
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(report.to_json() if args.json else report.to_text())
    return 2 if args.strict and not report.ok else 0


def _main_accessibility(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="mddocx accessibility",
        description="Audit a DOCX for common Word accessibility issues.",
    )
    p.add_argument("docx", type=Path)
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p.add_argument("--strict", action="store_true", help="Fail on medium-or-higher findings")
    p.add_argument("--fail-on", choices=["high", "medium", "low", "info"], default=None)
    args = p.parse_args(argv)
    try:
        report = audit_docx_accessibility(args.docx)
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(report.to_json() if args.json else report.to_text())
    threshold = args.fail_on or ("medium" if args.strict else "high")
    return 0 if report.passes(threshold) else 2


def _main_benchmark(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="mddocx benchmark",
        description="Run the deterministic large-document performance gate.",
    )
    p.add_argument("--sections", type=int, default=100)
    p.add_argument("--max-seconds", type=float, default=15.0)
    p.add_argument("--max-peak-mb", type=float, default=512.0)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    report = run_performance_gate(
        sections=max(1, args.sections),
        max_seconds=max(0.01, args.max_seconds),
        max_peak_memory_bytes=int(args.max_peak_mb * 1024 * 1024) if args.max_peak_mb > 0 else None,
    )
    print(report.to_json() if args.json else report.to_text())
    return 0 if report.ok else 2


def _main_api(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="mddocx api", description="Show the frozen mddocx v1 public API manifest."
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    manifest = get_public_api_manifest()
    if args.json:
        print(manifest.to_json())
    else:
        print(f"mddocx public API version: {manifest.api_version}")
        print(f"Package version: {manifest.package_version}")
        print(f"Frozen public names: {len(manifest.names)}")
        for name in manifest.names:
            print(f"  {name}")
    return 0


def _main_doctor(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="mddocx doctor",
        description="Check the local mddocx runtime and optional QA capabilities.",
    )
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = p.parse_args(argv)
    report = run_doctor()
    print(report.to_json() if args.json else report.to_text())
    return 0 if report.ok else 2


def _main_visual_qa(argv: list[str]) -> int:
    import tempfile

    p = argparse.ArgumentParser(
        prog="mddocx visual-qa",
        description="Render a DOCX to pages and compare it with a visual baseline.",
    )
    p.add_argument("docx", type=Path)
    p.add_argument("--baseline-dir", type=Path, required=True)
    p.add_argument("--threshold", type=float, default=0.985)
    p.add_argument("--dpi", type=int, default=144)
    p.add_argument(
        "--update-baseline",
        action="store_true",
        help="Replace the baseline with the current rendered pages",
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="mddocx-visual-pages-") as tmp:
            render_docx_pages(args.docx, tmp, dpi=args.dpi)
            if args.update_baseline:
                pages = update_visual_baseline(tmp, args.baseline_dir)
                print(f"Updated visual baseline with {len(pages)} page(s): {args.baseline_dir}")
                return 0
            report = compare_visual_pages(args.baseline_dir, tmp, threshold=args.threshold)
            print(report.to_json() if args.json else report.to_text())
            return 0 if report.ok else 2
    except (OSError, VisualQAUnavailable) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def _main_template(argv: list[str]) -> int:
    if not argv or argv[0] != "inspect":
        print("Usage: mddocx template inspect TEMPLATE.docx [--json]", file=sys.stderr)
        return 2
    p = argparse.ArgumentParser(
        prog="mddocx template inspect",
        description="Inspect a Word template's page setup, styles, and headers/footers.",
    )
    p.add_argument("template", type=Path)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv[1:])
    try:
        report = inspect_template(args.template)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(report.to_json() if args.json else report.to_text())
    return 0


def _resolve_project_output(manifest, raw: Path | None) -> Path | None:
    if raw is None:
        return None
    return raw.resolve() if raw.is_absolute() else (manifest.root / raw).resolve()


def _main_build(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="mddocx build", description="Build a multi-file mddocx project from mddocx.yml."
    )
    p.add_argument(
        "project", nargs="?", default=".", type=Path, help="Project directory or mddocx.yml"
    )
    p.add_argument("-o", "--output", type=Path, help="Override the project output path")
    p.add_argument(
        "--force", action="store_true", help="Rebuild even when all dependencies are unchanged"
    )
    p.add_argument(
        "--check", action="store_true", help="Parse the complete project without writing DOCX"
    )
    p.add_argument("--json", action="store_true", help="Emit machine-readable build information")
    p.add_argument("--open", action="store_true", help="Open the generated project DOCX")
    args = p.parse_args(argv)
    try:
        manifest = load_project(args.project)
        if args.check:
            compiled = compile_project(manifest)
            payload = {
                "manifest": str(manifest.path),
                "sources": compiled.source_count,
                "includes": compiled.include_count,
                "dependencies": [str(x) for x in compiled.dependencies],
            }
            if args.json:
                import json

                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print(f"OK {manifest.path}")
                print(f"Sources: {compiled.source_count}")
                print(f"Includes: {compiled.include_count}")
                print(f"Dependencies: {len(compiled.dependencies)}")
            return 0
        result = build_project(
            manifest,
            output=_resolve_project_output(manifest, args.output),
            force=args.force,
        )
        if args.json:
            print(result.to_json())
        else:
            status = "BUILT" if result.built else "UP-TO-DATE"
            print(f"{status} {result.output_path}")
            print(f"Dependencies: {len(result.dependencies)}")
            print(f"Fingerprint: {result.fingerprint}")
        add_recent(
            source=result.project_file,
            output=result.output_path,
            action="build",
            workspace=manifest.root,
            settings={"fingerprint": result.fingerprint},
        )
        if args.open:
            open_path(result.output_path)
        return 0
    except (MddocxError, OSError, ValueError) as exc:
        print(exc if isinstance(exc, MddocxError) else f"ERROR: {exc}", file=sys.stderr)
        return 2


def _main_watch(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="mddocx watch", description="Watch a project and rebuild its DOCX when inputs change."
    )
    p.add_argument(
        "project", nargs="?", default=".", type=Path, help="Project directory or mddocx.yml"
    )
    p.add_argument("-o", "--output", type=Path, help="Override the project output path")
    p.add_argument("--interval", type=float, help="Polling interval in seconds")
    p.add_argument(
        "--once", action="store_true", help="Build once using the watch pipeline, then exit"
    )
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)
    try:
        manifest = load_project(args.project)
        output = _resolve_project_output(manifest, args.output)

        def show(event: ProjectWatchEvent) -> None:
            if args.quiet:
                return
            if event.kind == "change":
                names = ", ".join(
                    str(p.relative_to(manifest.root)) if p.is_relative_to(manifest.root) else str(p)
                    for p in event.changed[:8]
                )
                extra = " ..." if len(event.changed) > 8 else ""
                print(f"CHANGE {names}{extra}")
            elif event.kind == "build" and event.result is not None:
                status = "BUILT" if event.result.built else "UP-TO-DATE"
                print(f"{status} {event.result.output_path}")
            elif event.kind == "error":
                print(f"ERROR: {event.error}", file=sys.stderr)

        watch_project(
            manifest,
            interval=args.interval,
            output=output,
            once=args.once,
            on_event=show,
        )
        return 0
    except KeyboardInterrupt:
        if not args.quiet:
            print("Stopped.")
        return 0
    except (MddocxError, OSError, ValueError) as exc:
        print(exc if isinstance(exc, MddocxError) else f"ERROR: {exc}", file=sys.stderr)
        return 2


def _main_project(argv: list[str]) -> int:
    if not argv:
        print("Usage: mddocx project {init|info} ...", file=sys.stderr)
        return 2
    command = argv[0]
    if command == "init":
        p = argparse.ArgumentParser(
            prog="mddocx project init", description="Create a starter mddocx.yml project."
        )
        p.add_argument("directory", nargs="?", default=".", type=Path)
        p.add_argument("--force", action="store_true", help="Replace an existing mddocx.yml")
        args = p.parse_args(argv[1:])
        try:
            path = init_project(args.directory, force=args.force)
            print(path)
            return 0
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    if command == "info":
        p = argparse.ArgumentParser(
            prog="mddocx project info",
            description="Show project sources and resolved dependencies.",
        )
        p.add_argument("project", nargs="?", default=".", type=Path)
        p.add_argument("--json", action="store_true")
        args = p.parse_args(argv[1:])
        try:
            info = project_info(args.project)
            if args.json:
                import json

                print(json.dumps(info, indent=2, ensure_ascii=False))
            else:
                print(f"Manifest: {info['manifest']}")
                print(f"Output: {info['output']}")
                print(f"Sources: {info['source_count']}")
                print(f"Includes: {info['include_count']}")
                print("Dependencies:")
                for dep in info["dependencies"]:
                    print(f"  {dep}")
            return 0
        except (MddocxError, OSError, ValueError) as exc:
            print(exc if isinstance(exc, MddocxError) else f"ERROR: {exc}", file=sys.stderr)
            return 2
    print(f"Unknown project command: {command}", file=sys.stderr)
    return 2


def _main_data(argv: list[str]) -> int:
    if not argv or argv[0] != "inspect":
        print("Usage: mddocx data inspect DATA.{csv,json} [--json]", file=sys.stderr)
        return 2
    p = argparse.ArgumentParser(
        prog="mddocx data inspect",
        description="Inspect a CSV/JSON data source before using it in a chart or imported table.",
    )
    p.add_argument("data", type=Path)
    p.add_argument("--json", action="store_true")
    p.add_argument("--max-rows", type=int, default=10_000)
    p.add_argument("--max-columns", type=int, default=100)
    args = p.parse_args(argv[1:])
    try:
        data = load_tabular_data(args.data, max_rows=args.max_rows, max_columns=args.max_columns)
    except (MddocxError, OSError, ValueError) as exc:
        print(exc if isinstance(exc, MddocxError) else f"ERROR: {exc}", file=sys.stderr)
        return 2
    payload = {"path": str(args.data), "columns": data.columns, "rows": len(data.rows)}
    if args.json:
        import json

        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Data source: {args.data}")
        print(f"Rows: {len(data.rows)}")
        print(f"Columns ({len(data.columns)}): {', '.join(data.columns)}")
    return 0


def _main_metadata(argv: list[str]) -> int:
    if not argv or argv[0] not in {"inspect", "clean"}:
        print(
            "Usage: mddocx metadata inspect FILE [--policy auto|strip|keep] [--json]\n       mddocx metadata clean FILE -o CLEAN.md [--policy auto|strip|keep]",
            file=sys.stderr,
        )
        return 2
    command = argv[0]
    p = argparse.ArgumentParser(
        prog=f"mddocx metadata {command}",
        description="Inspect or remove AI/chat export metadata from Markdown without executing or rendering it.",
    )
    p.add_argument("markdown", type=Path)
    p.add_argument("--policy", choices=["auto", "strip", "keep"], default="auto")
    p.add_argument("--json", action="store_true")
    if command == "clean":
        p.add_argument("-o", "--output", required=True, type=Path)
    args = p.parse_args(argv[1:])
    try:
        raw = args.markdown.read_text(encoding="utf-8-sig")
        result = sanitize_markdown_metadata(raw, MetadataConfig(ai_export=args.policy))
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if command == "clean":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.markdown, encoding="utf-8")
        if args.json:
            payload = result.report.to_dict() | {"output": str(args.output)}
            import json as _json

            print(_json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(args.output)
        return 0
    if args.json:
        print(result.report.to_json())
    else:
        r = result.report
        print(f"Policy: {r.policy}")
        print(f"AI/export metadata detected: {'yes' if r.detected_export_metadata else 'no'}")
        print(f"Removed source lines: {r.removed_lines}")
        print(f"Removed blocks: {r.removed_blocks}")
        print(
            f"Removed front-matter fields: {', '.join(r.removed_front_matter_keys) if r.removed_front_matter_keys else '(none)'}"
        )
        if r.reasons:
            print("Reasons:")
            for reason in r.reasons:
                print(f"  - {reason}")
    return 0


def _main_math_check(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="mddocx math-check",
        description="Inspect equations before DOCX conversion.",
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 3 when any equation needs a fallback",
    )
    args = parser.parse_args(argv)
    try:
        report = inspect_math_file(args.input)
    except (OSError, ValueError, MddocxError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(report.to_json() if args.json else report.to_text())
    return 3 if args.strict and not report.ok else 0


def _main_shell(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="mddocx shell", description="Open the interactive mddocx console."
    )
    p.add_argument("workspace", nargs="?", default=".", type=Path)
    p.add_argument("--no-menu", action="store_true", help="Start directly at the REPL prompt")
    args = p.parse_args(argv)
    try:
        return run_shell(args.workspace, show_menu=not args.no_menu)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def _main_recent(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="mddocx recent",
        description="Show recently generated DOCX files. Paths/settings only are stored; document content is never stored.",
    )
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    items = load_recent(limit=max(0, args.limit))
    if args.json:
        import json
        from dataclasses import asdict

        print(json.dumps([asdict(item) for item in items], indent=2, ensure_ascii=False))
    else:
        if not items:
            print("No recent mddocx outputs recorded.")
        for index, item in enumerate(items, start=1):
            print(f"{index}. {item.source} -> {item.output} [{item.action}] {item.created_at}")
    return 0


def _main_open(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="mddocx open",
        description="Open a DOCX using the operating-system default application.",
    )
    p.add_argument("docx", nargs="?", type=Path)
    args = p.parse_args(argv)
    target = args.docx
    if target is None:
        recent = load_recent(limit=1)
        if not recent:
            print("ERROR: no recent DOCX is available", file=sys.stderr)
            return 2
        target = Path(recent[0].output)
    try:
        open_path(target)
        print(target)
        return 0
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] == "shell":
        return _main_shell(raw[1:])
    if raw and raw[0] == "recent":
        return _main_recent(raw[1:])
    if raw and raw[0] == "open":
        return _main_open(raw[1:])
    if raw and raw[0] == "build":
        return _main_build(raw[1:])
    if raw and raw[0] == "watch":
        return _main_watch(raw[1:])
    if raw and raw[0] == "project":
        return _main_project(raw[1:])
    if raw and raw[0] == "inspect":
        return _main_inspect(raw[1:])
    if raw and raw[0] == "doctor":
        return _main_doctor(raw[1:])
    if raw and raw[0] == "accessibility":
        return _main_accessibility(raw[1:])
    if raw and raw[0] == "benchmark":
        return _main_benchmark(raw[1:])
    if raw and raw[0] == "api":
        return _main_api(raw[1:])
    if raw and raw[0] == "visual-qa":
        return _main_visual_qa(raw[1:])
    if raw and raw[0] == "template":
        return _main_template(raw[1:])
    if raw and raw[0] == "data":
        return _main_data(raw[1:])
    if raw and raw[0] == "metadata":
        return _main_metadata(raw[1:])
    if raw and raw[0] == "math-check":
        return _main_math_check(raw[1:])
    args = build_parser().parse_args(raw)
    config = _config_from_args(args)
    try:
        sources = collect_markdown_inputs(args.input, recursive=args.recursive)
        if not sources:
            print("ERROR: no Markdown inputs found", file=sys.stderr)
            return 2

        batch_mode = (
            len(sources) > 1 or any(p.is_dir() for p in args.input) or args.output_dir is not None
        )
        if args.check:
            status = 0
            for source in sources:
                converter = MarkdownWord(config)
                try:
                    converter.check_file(source)
                    print(source)
                except MddocxError as exc:
                    print(exc, file=sys.stderr)
                    status = 2
                    if args.fail_fast:
                        break
            return status

        if batch_mode:
            if args.output is not None:
                print(
                    "ERROR: --output cannot be combined with batch conversion; use --output-dir",
                    file=sys.stderr,
                )
                return 2
            output_dir = args.output_dir or Path(".")
            results = render_many(sources, output_dir, config, fail_fast=args.fail_fast)
            status = 0
            for result in results:
                if result.ok:
                    print(result.output_path)
                else:
                    print(f"ERROR {result.input_path}: {result.error}", file=sys.stderr)
                    status = 2
            return status

        source = sources[0]
        converter = MarkdownWord(config)
        output = args.output or source.with_suffix(".docx")
        converter.render_file(source, output)
        print(output)
        add_recent(
            source=source,
            output=output,
            action="render",
            workspace=Path.cwd(),
            settings={"theme": args.theme},
        )
        if args.open:
            open_path(output)
        _write_text_target(args.diagnostics_json, converter.diagnostics_json())
        _write_text_target(args.diagnostics_sarif, converter.diagnostics_sarif())
        if args.profile or args.profile_memory:
            print(converter.last_stats.to_json())
        return 0
    except MddocxError as exc:
        print(exc, file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
