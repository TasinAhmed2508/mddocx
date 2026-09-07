from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
import hashlib
import json
import glob as _glob
from pathlib import Path
import re
import time
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

from .api import MarkdownWord, _apply_front_matter
from .ast.base import Document, Node
from .ast.block import ImageBlock, ChartBlock, DataTableBlock
from .ast.inline import Image
from .config import RenderConfig
from .diagnostics import Diagnostic, MddocxError
from .normalize import Normalizer
from .parser import MarkdownParser
from .parser.frontmatter import split_front_matter
from .metadata import sanitize_markdown_metadata

_PROJECT_SCHEMA_VERSION = 1
_PROJECT_ENGINE_VERSION = "mddocx-project-v2"
_INCLUDE_RE = re.compile(
    r"^[ \t]{0,3}@include[ \t]+(?:\"(?P<double>[^\"]+)\"|'(?P<single>[^']+)'|(?P<bare>[^\s#]+))[ \t]*$"
)
_FENCE_RE = re.compile(r"^[ \t]{0,3}(?P<marker>`{3,}|~{3,})")
_VAR_RE = re.compile(r"(?<!\\)\{\{\s*(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}")
_ESCAPED_VAR_RE = re.compile(r"\\(\{\{\s*[A-Za-z_][A-Za-z0-9_.-]*\s*\}\})")
_MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd"}


@dataclass(slots=True)
class ProjectManifest:
    path: Path
    root: Path
    sources: tuple[Path, ...]
    output: Path
    variables: dict[str, str] = field(default_factory=dict)
    render: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    max_include_depth: int = 32
    undefined_variables: str = "error"
    watch_interval: float = 1.0


@dataclass(slots=True)
class ProjectCompilation:
    document: Document
    dependencies: tuple[Path, ...]
    source_count: int
    include_count: int


@dataclass(slots=True)
class ProjectBuildResult:
    project_file: Path
    output_path: Path
    built: bool
    skipped: bool
    dependencies: tuple[Path, ...]
    fingerprint: str
    output_sha256: str
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_file": str(self.project_file),
            "output_path": str(self.output_path),
            "built": self.built,
            "skipped": self.skipped,
            "dependencies": [str(p) for p in self.dependencies],
            "fingerprint": self.fingerprint,
            "output_sha256": self.output_sha256,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass(slots=True)
class ProjectWatchEvent:
    kind: str
    result: ProjectBuildResult | None = None
    changed: tuple[Path, ...] = ()
    error: str | None = None


class ProjectCompiler:
    def __init__(self, manifest: ProjectManifest, config: RenderConfig | None = None):
        self.manifest = manifest
        self.config = _config_from_manifest(manifest, config)
        self.parser = MarkdownParser(self.config.extensions, self.config.metadata)
        self.normalizer = Normalizer()
        self._dependencies: set[Path] = {manifest.path.resolve()}
        self._stack: list[Path] = []
        self._include_count = 0
        self._document_metadata: dict[str, Any] = {}
        self._have_primary_metadata = False

    def compile(self) -> ProjectCompilation:
        children: list[Any] = []
        footnotes: dict[str, list[Any]] = {}
        for source in self.manifest.sources:
            doc = self._compile_file(source, depth=0)
            if not self._have_primary_metadata and doc.metadata:
                self._document_metadata.update(doc.metadata)
                self._have_primary_metadata = True
            children.extend(doc.children)
            self._merge_footnotes(footnotes, doc.footnotes, source)
        self._document_metadata.update(self.manifest.metadata)
        document = Document(children=children, metadata=self._document_metadata, footnotes=footnotes)
        document = self.normalizer.normalize(document)
        return ProjectCompilation(
            document=document,
            dependencies=tuple(sorted(self._dependencies, key=lambda p: str(p).casefold())),
            source_count=len(self.manifest.sources),
            include_count=self._include_count,
        )

    def _compile_file(self, path: Path, depth: int) -> Document:
        path = path.resolve()
        if depth > self.manifest.max_include_depth:
            raise _project_error("PROJECT804", f"Include depth exceeds {self.manifest.max_include_depth}.", path)
        _ensure_within(self.manifest.root, path, "PROJECT802", "Included source escapes the project root")
        if path.suffix.lower() not in _MARKDOWN_SUFFIXES:
            raise _project_error("PROJECT803", f"Included file must be Markdown: {path.name}", path)
        if not path.is_file():
            raise _project_error("PROJECT801", f"Project source not found: {path}", path)
        if path in self._stack:
            cycle = " -> ".join([p.name for p in self._stack + [path]])
            raise _project_error("PROJECT805", f"Include cycle detected: {cycle}", path)
        self._dependencies.add(path)
        self._stack.append(path)
        try:
            raw = path.read_text(encoding="utf-8-sig")
            sanitized = sanitize_markdown_metadata(raw, self.config.metadata)
            metadata, body, front_offset = split_front_matter(sanitized.markdown)
            chunks = _split_include_chunks(body)
            children: list[Any] = []
            footnotes: dict[str, list[Any]] = {}
            for chunk in chunks:
                if chunk[0] == "text":
                    _, text, body_line = chunk
                    if not text.strip():
                        continue
                    expanded = _substitute_variables(
                        text,
                        self.manifest.variables,
                        self.manifest.undefined_variables,
                        path,
                        front_offset + body_line,
                    )
                    parsed = self.parser.parse(
                        expanded,
                        source_file=str(path),
                        base_line_offset=front_offset + body_line - 1,
                        sanitize_metadata=False,
                    )
                    self._rewrite_local_resources(parsed, path.parent)
                    children.extend(parsed.children)
                    self._merge_footnotes(footnotes, parsed.footnotes, path)
                else:
                    _, include_text, line_no = chunk
                    include_text = _substitute_variables(
                        include_text,
                        self.manifest.variables,
                        self.manifest.undefined_variables,
                        path,
                        front_offset + line_no,
                    )
                    include_path = _resolve_project_path(
                        self.manifest.root,
                        path.parent,
                        include_text,
                        "PROJECT802",
                        f"Include path escapes the project root at {path.name}:{front_offset + line_no}",
                    )
                    self._include_count += 1
                    nested = self._compile_file(include_path, depth + 1)
                    children.extend(nested.children)
                    self._merge_footnotes(footnotes, nested.footnotes, include_path)
            return Document(children=children, metadata=metadata, footnotes=footnotes)
        finally:
            self._stack.pop()

    def _rewrite_local_resources(self, document: Document, source_dir: Path) -> None:
        for node in _walk_nodes(document):
            if isinstance(node, (ImageBlock, Image)):
                source = node.src
                parsed = urlparse(source)
                if parsed.scheme or parsed.netloc or source.startswith("#"):
                    continue
                target = (source_dir / source).resolve()
                self._dependencies.add(target)
                _ensure_within(
                    self.manifest.root, target, "PROJECT806",
                    f"Resource referenced by project source escapes the project root: {source}",
                )
                node.src = target.relative_to(self.manifest.root).as_posix()
            elif isinstance(node, ChartBlock) and node.source_path:
                source = node.source_path
                parsed = urlparse(source)
                if parsed.scheme or parsed.netloc:
                    raise _project_error("PROJECT827", "Chart data sources must be local project files.", Path(getattr(node.source, "file", self.manifest.path)))
                target = (source_dir / source).resolve()
                self._dependencies.add(target)
                _ensure_within(self.manifest.root, target, "PROJECT806", f"Chart data source escapes the project root: {source}")
                node.source_path = target.relative_to(self.manifest.root).as_posix()
            elif isinstance(node, DataTableBlock):
                source = node.source_path
                parsed = urlparse(source)
                if parsed.scheme or parsed.netloc:
                    raise _project_error("PROJECT827", "Data-table sources must be local project files.", Path(getattr(node.source, "file", self.manifest.path)))
                target = (source_dir / source).resolve()
                self._dependencies.add(target)
                _ensure_within(self.manifest.root, target, "PROJECT806", f"Data-table source escapes the project root: {source}")
                node.source_path = target.relative_to(self.manifest.root).as_posix()

    @staticmethod
    def _merge_footnotes(target: dict[str, list[Any]], incoming: dict[str, list[Any]], source: Path) -> None:
        for label, nodes in incoming.items():
            if label in target:
                raise _project_error("PROJECT807", f"Duplicate footnote label across project sources: {label}", source)
            target[label] = nodes


def load_project(project: str | Path = ".") -> ProjectManifest:
    path = Path(project)
    if path.is_dir():
        path = path / "mddocx.yml"
    path = path.resolve()
    if not path.is_file():
        raise _project_error("PROJECT800", f"Project manifest not found: {path}", path)
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise _project_error("PROJECT809", "Project mode requires PyYAML.", path) from exc
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise _project_error("PROJECT810", f"Unable to parse project YAML: {type(exc).__name__}", path) from exc
    if not isinstance(loaded, dict):
        raise _project_error("PROJECT811", "Project manifest must contain a YAML mapping.", path)
    version = loaded.get("version", _PROJECT_SCHEMA_VERSION)
    if version != _PROJECT_SCHEMA_VERSION:
        raise _project_error("PROJECT812", f"Unsupported project manifest version: {version}", path)
    root = path.parent.resolve()
    raw_sources = loaded.get("sources")
    if isinstance(raw_sources, str):
        raw_sources = [raw_sources]
    if not isinstance(raw_sources, list) or not raw_sources:
        raise _project_error("PROJECT813", "Project manifest requires a non-empty 'sources' list.", path)
    sources: list[Path] = []
    for item in raw_sources:
        if not isinstance(item, str) or not item.strip():
            raise _project_error("PROJECT813", "Every project source must be a non-empty path string.", path)
        if _glob.has_magic(item):
            pattern_path = Path(item)
            if pattern_path.is_absolute() or ".." in pattern_path.parts:
                raise _project_error("PROJECT814", "Project source glob escapes the project root", path)
            matches = sorted(
                (candidate.resolve() for candidate in root.glob(item) if candidate.is_file()),
                key=lambda candidate: str(candidate).casefold(),
            )
            if not matches:
                raise _project_error("PROJECT826", f"Project source glob matched no files: {item}", path)
            for candidate in matches:
                _ensure_within(root, candidate, "PROJECT814", "Project source escapes the project root")
                if candidate.suffix.lower() not in _MARKDOWN_SUFFIXES:
                    continue
                if candidate not in sources:
                    sources.append(candidate)
        else:
            candidate = _resolve_manifest_path(root, item, "PROJECT814", "Project source escapes the project root")
            if candidate not in sources:
                sources.append(candidate)
    if not sources:
        raise _project_error("PROJECT826", "Project sources did not resolve to any Markdown files.", path)

    output_raw = loaded.get("output", "build/document.docx")
    if not isinstance(output_raw, str) or not output_raw.strip():
        raise _project_error("PROJECT815", "Project output must be a path string.", path)
    output = _resolve_manifest_path(root, output_raw, "PROJECT816", "Project output escapes the project root")
    if output.suffix.lower() != ".docx":
        raise _project_error("PROJECT817", "Project output must use the .docx extension.", path)

    variables_raw = loaded.get("variables") or {}
    if not isinstance(variables_raw, dict):
        raise _project_error("PROJECT818", "Project variables must be a YAML mapping.", path)
    variables: dict[str, str] = {}
    for key, value in variables_raw.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", key):
            raise _project_error("PROJECT819", f"Invalid project variable name: {key!r}", path)
        if isinstance(value, (dict, list, tuple, set)):
            raise _project_error("PROJECT820", f"Project variable '{key}' must be scalar.", path)
        rendered = "" if value is None else str(value)
        if "\n" in rendered or "\r" in rendered:
            raise _project_error("PROJECT820", f"Project variable '{key}' may not contain newlines.", path)
        variables[key] = rendered

    render = loaded.get("render") or {}
    metadata = loaded.get("metadata") or {}
    if not isinstance(render, dict) or not isinstance(metadata, dict):
        raise _project_error("PROJECT821", "'render' and 'metadata' must be YAML mappings.", path)
    project_cfg = loaded.get("project") or {}
    if project_cfg and not isinstance(project_cfg, dict):
        raise _project_error("PROJECT822", "'project' must be a YAML mapping.", path)
    watch_cfg = loaded.get("watch") or {}
    if watch_cfg and not isinstance(watch_cfg, dict):
        raise _project_error("PROJECT823", "'watch' must be a YAML mapping.", path)
    max_depth = int(project_cfg.get("max_include_depth", 32))
    max_depth = max(1, min(256, max_depth))
    undefined = str(project_cfg.get("undefined_variables", "error"))
    if undefined not in {"error", "keep", "empty"}:
        raise _project_error("PROJECT824", "undefined_variables must be error, keep, or empty.", path)
    interval = float(watch_cfg.get("interval", 1.0))
    if interval < 0.1:
        interval = 0.1
    return ProjectManifest(
        path=path,
        root=root,
        sources=tuple(sources),
        output=output,
        variables=variables,
        render=dict(render),
        metadata=dict(metadata),
        max_include_depth=max_depth,
        undefined_variables=undefined,
        watch_interval=interval,
    )


def compile_project(project: str | Path | ProjectManifest = ".", config: RenderConfig | None = None) -> ProjectCompilation:
    manifest = project if isinstance(project, ProjectManifest) else load_project(project)
    return ProjectCompiler(manifest, config=config).compile()


def build_project(
    project: str | Path | ProjectManifest = ".",
    config: RenderConfig | None = None,
    *,
    output: str | Path | None = None,
    force: bool = False,
) -> ProjectBuildResult:
    start = time.perf_counter()
    manifest = project if isinstance(project, ProjectManifest) else load_project(project)
    output_path = Path(output).resolve() if output is not None else manifest.output
    state_path = manifest.root / ".mddocx" / "build-state.json"
    if not force:
        current = _try_current_state(manifest, state_path, output_path)
        if current is not None:
            return ProjectBuildResult(
                project_file=manifest.path,
                output_path=output_path,
                built=False,
                skipped=True,
                dependencies=current[0],
                fingerprint=current[1],
                output_sha256=current[2],
                elapsed_ms=(time.perf_counter() - start) * 1000,
            )

    compiler = ProjectCompiler(manifest, config=config)
    compiled = compiler.compile()
    cfg = compiler.config
    cfg.base_dir = manifest.root
    converter = MarkdownWord(cfg)
    blob = converter.render_ast(compiled.document, base_dir=manifest.root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(blob)

    dependencies = set(compiled.dependencies)
    dependencies.update(_render_dependencies(manifest, cfg))
    dependency_tuple = tuple(sorted((p.resolve() for p in dependencies), key=lambda p: str(p).casefold()))
    fingerprint = _fingerprint(manifest.path, dependency_tuple)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    output_sha256 = hashlib.sha256(blob).hexdigest()
    state = {
        "schema": 1,
        "engine": _PROJECT_ENGINE_VERSION,
        "manifest": str(manifest.path),
        "output": str(output_path),
        "dependencies": [str(p) for p in dependency_tuple],
        "fingerprint": fingerprint,
        "output_sha256": output_sha256,
    }
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ProjectBuildResult(
        project_file=manifest.path,
        output_path=output_path,
        built=True,
        skipped=False,
        dependencies=dependency_tuple,
        fingerprint=fingerprint,
        output_sha256=output_sha256,
        elapsed_ms=(time.perf_counter() - start) * 1000,
    )


def watch_project(
    project: str | Path | ProjectManifest = ".",
    config: RenderConfig | None = None,
    *,
    interval: float | None = None,
    output: str | Path | None = None,
    once: bool = False,
    on_event: Callable[[ProjectWatchEvent], None] | None = None,
) -> None:
    manifest = project if isinstance(project, ProjectManifest) else load_project(project)
    delay = max(0.1, interval if interval is not None else manifest.watch_interval)

    def emit(event: ProjectWatchEvent) -> None:
        if on_event:
            on_event(event)

    try:
        result = build_project(manifest, config=config, output=output)
        emit(ProjectWatchEvent("build", result=result))
    except Exception as exc:
        emit(ProjectWatchEvent("error", error=str(exc)))
        if once:
            raise
    if once:
        return

    watched_output = Path(output).resolve() if output is not None else manifest.output.resolve()
    before = _watch_snapshot(manifest.root, ignore={watched_output})
    while True:
        time.sleep(delay)
        after = _watch_snapshot(manifest.root, ignore={watched_output})
        changed = tuple(sorted(set(before) ^ set(after) | {p for p in before.keys() & after.keys() if before[p] != after[p]}, key=lambda p: str(p).casefold()))
        if not changed:
            continue
        before = after
        emit(ProjectWatchEvent("change", changed=changed))
        try:
            # Reload because the manifest itself may have changed.
            manifest = load_project(manifest.path)
            watched_output = Path(output).resolve() if output is not None else manifest.output.resolve()
            result = build_project(manifest, config=config, output=output)
            before = _watch_snapshot(manifest.root, ignore={watched_output})
            emit(ProjectWatchEvent("build", result=result, changed=changed))
        except Exception as exc:
            emit(ProjectWatchEvent("error", changed=changed, error=str(exc)))


def init_project(directory: str | Path, *, force: bool = False) -> Path:
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / "mddocx.yml"
    if manifest.exists() and not force:
        raise FileExistsError(manifest)
    chapter_dir = root / "chapters"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    intro = chapter_dir / "01-introduction.md"
    if not intro.exists():
        intro.write_text("# Introduction\n\nWelcome to {{ project_name }}.\n", encoding="utf-8")
    manifest.write_text(
        """version: 1
output: build/document.docx
sources:
  - chapters/01-introduction.md
variables:
  project_name: My Document
render:
  title: My Document
  title_page: true
  toc: true
  heading_numbering: true
  page_x_of_y: true
  ai_metadata: auto
project:
  max_include_depth: 32
  undefined_variables: error
watch:
  interval: 1.0
""",
        encoding="utf-8",
    )
    return manifest


def project_info(project: str | Path | ProjectManifest = ".") -> dict[str, Any]:
    manifest = project if isinstance(project, ProjectManifest) else load_project(project)
    compilation = ProjectCompiler(manifest).compile()
    return {
        "manifest": str(manifest.path),
        "root": str(manifest.root),
        "output": str(manifest.output),
        "sources": [str(p) for p in manifest.sources],
        "variables": dict(manifest.variables),
        "dependencies": [str(p) for p in compilation.dependencies],
        "source_count": compilation.source_count,
        "include_count": compilation.include_count,
    }


def _config_from_manifest(manifest: ProjectManifest, explicit: RenderConfig | None) -> RenderConfig:
    cfg = deepcopy(explicit) if explicit is not None else RenderConfig()
    cfg = _apply_front_matter(cfg, manifest.render, explicit_config=explicit is not None)
    # Project render keys that are intentionally not part of Markdown front matter.
    render = manifest.render
    if explicit is None:
        if "template" in render and render["template"]:
            cfg.template = _resolve_manifest_path(manifest.root, str(render["template"]), "PROJECT825", "Template path escapes the project root")
        if "font" in render:
            cfg.fonts.body = str(render["font"])
        if "heading_font" in render:
            cfg.fonts.headings = str(render["heading_font"])
        if "code_font" in render:
            cfg.fonts.code = str(render["code_font"])
        if "code_language_labels" in render:
            cfg.code.show_language_label = bool(render["code_language_labels"])
        if "syntax_highlighting" in render:
            cfg.code.syntax_highlighting = bool(render["syntax_highlighting"])
        if render.get("ai_metadata") in {"auto", "strip", "keep"}:
            cfg.metadata.ai_export = str(render["ai_metadata"])
        if "different_first_page" in render:
            cfg.header.different_first_page = bool(render["different_first_page"])
            cfg.footer.different_first_page = bool(render["different_first_page"])
        if "different_odd_even" in render:
            cfg.header.different_odd_even = bool(render["different_odd_even"])
            cfg.footer.different_odd_even = bool(render["different_odd_even"])
        if "header" in render:
            cfg.header.text = str(render["header"]); cfg.header.enabled = True
        if "footer" in render:
            cfg.footer.text = str(render["footer"]); cfg.footer.enabled = True
        if "num_pages" in render:
            cfg.footer.num_pages = bool(render["num_pages"]); cfg.footer.enabled = cfg.footer.enabled or cfg.footer.num_pages
        if "auto_bibliography" in render:
            cfg.citations.auto_bibliography = bool(render["auto_bibliography"])
        if "bibliography" in render and render["bibliography"]:
            cfg.citations.bibliography = Path(str(render["bibliography"]))
    cfg.base_dir = manifest.root
    return cfg


def _render_dependencies(manifest: ProjectManifest, cfg: RenderConfig) -> set[Path]:
    deps: set[Path] = set()
    if cfg.template:
        path = Path(cfg.template)
        if not path.is_absolute():
            path = manifest.root / path
        deps.add(path.resolve())
    if cfg.citations.bibliography:
        path = Path(cfg.citations.bibliography)
        if not path.is_absolute():
            path = manifest.root / path
        deps.add(path.resolve())
    return {p for p in deps if p.exists()}


def _split_include_chunks(body: str) -> list[tuple[str, str, int]]:
    lines = body.splitlines(keepends=True)
    chunks: list[tuple[str, str, int]] = []
    buffer: list[str] = []
    buffer_start = 1
    fence: str | None = None

    def flush() -> None:
        nonlocal buffer, buffer_start
        if buffer:
            chunks.append(("text", "".join(buffer), buffer_start))
            buffer = []

    for index, line in enumerate(lines, start=1):
        stripped = line.rstrip("\r\n")
        fence_match = _FENCE_RE.match(stripped)
        if fence_match:
            marker = fence_match.group("marker")
            if fence is None:
                fence = marker[0]
            elif marker[0] == fence:
                fence = None
            if not buffer:
                buffer_start = index
            buffer.append(line)
            continue
        match = _INCLUDE_RE.match(stripped) if fence is None else None
        if match:
            flush()
            include = match.group("double") or match.group("single") or match.group("bare") or ""
            chunks.append(("include", include, index))
            buffer_start = index + 1
        else:
            if not buffer:
                buffer_start = index
            buffer.append(line)
    flush()
    if not lines and body:
        chunks.append(("text", body, 1))
    return chunks


def _substitute_variables(
    text: str,
    variables: dict[str, str],
    policy: str,
    source: Path,
    base_line: int,
) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name in variables:
            return variables[name]
        if policy == "keep":
            return match.group(0)
        if policy == "empty":
            return ""
        line = base_line + text.count("\n", 0, match.start())
        raise _project_error("PROJECT808", f"Undefined project variable: {name}", source, line)

    rendered = _VAR_RE.sub(replace, text)
    return _ESCAPED_VAR_RE.sub(lambda m: m.group(1), rendered)


def _walk_nodes(value: Any) -> Iterable[Any]:
    seen: set[int] = set()

    def walk(item: Any):
        if isinstance(item, (str, bytes, int, float, bool, type(None), Path)):
            return
        ident = id(item)
        if ident in seen:
            return
        seen.add(ident)
        if isinstance(item, Node):
            yield item
        if isinstance(item, dict):
            for v in item.values():
                yield from walk(v)
        elif isinstance(item, (list, tuple, set)):
            for v in item:
                yield from walk(v)
        elif is_dataclass(item):
            for f in fields(item):
                if f.name == "source":
                    continue
                yield from walk(getattr(item, f.name))

    yield from walk(value)


def _resolve_manifest_path(root: Path, raw: str, code: str, message: str) -> Path:
    candidate_raw = Path(raw)
    if candidate_raw.is_absolute():
        raise _project_error(code, message)
    candidate = (root / candidate_raw).resolve()
    _ensure_within(root, candidate, code, message)
    return candidate


def _resolve_project_path(root: Path, parent: Path, raw: str, code: str, message: str) -> Path:
    candidate_raw = Path(raw)
    if candidate_raw.is_absolute():
        raise _project_error(code, message)
    candidate = (parent / candidate_raw).resolve()
    _ensure_within(root, candidate, code, message)
    return candidate


def _ensure_within(root: Path, candidate: Path, code: str, message: str) -> None:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise _project_error(code, message, candidate) from exc


def _project_error(code: str, message: str, source: Path | None = None, line: int | None = None) -> MddocxError:
    return MddocxError(Diagnostic("error", code, message, str(source) if source else None, line))


def _fingerprint(manifest_path: Path, dependencies: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    digest.update(_PROJECT_ENGINE_VERSION.encode("utf-8"))
    paths = {manifest_path.resolve(), *(p.resolve() for p in dependencies)}
    for path in sorted(paths, key=lambda p: str(p).casefold()):
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        if path.is_file():
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        else:
            digest.update(b"MISSING")
        digest.update(b"\0")
    return digest.hexdigest()


def _try_current_state(manifest: ProjectManifest, state_path: Path, output_path: Path) -> tuple[tuple[Path, ...], str, str] | None:
    if not state_path.is_file() or not output_path.is_file():
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("schema") != 1 or state.get("engine") != _PROJECT_ENGINE_VERSION:
            return None
        if Path(state.get("manifest", "")).resolve() != manifest.path.resolve():
            return None
        if Path(state.get("output", "")).resolve() != output_path.resolve():
            return None
        deps = tuple(Path(p).resolve() for p in state.get("dependencies", []))
        fingerprint = _fingerprint(manifest.path, deps)
        if fingerprint != state.get("fingerprint"):
            return None
        expected_output_hash = str(state.get("output_sha256") or "")
        if not expected_output_hash or hashlib.sha256(output_path.read_bytes()).hexdigest() != expected_output_hash:
            return None
        return deps, fingerprint, expected_output_hash
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _watch_snapshot(root: Path, *, ignore: set[Path] | None = None) -> dict[Path, tuple[int, int]]:
    snapshot: dict[Path, tuple[int, int]] = {}
    ignored = {p.resolve() for p in (ignore or set())}
    count = 0
    for path in root.rglob("*"):
        if count >= 20_000:
            break
        if not path.is_file():
            continue
        if path.resolve() in ignored:
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] in {".mddocx", ".git", ".venv", "__pycache__"}:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        snapshot[path.resolve()] = (stat.st_mtime_ns, stat.st_size)
        count += 1
    return snapshot
