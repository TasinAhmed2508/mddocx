from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_MD_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
_DATA_SUFFIXES = {".csv", ".json"}
_TEMPLATE_SUFFIXES = {".docx", ".dotx"}
_SKIP_DIRS = {".git", ".mddocx", ".venv", "venv", "node_modules", "__pycache__", "build", "dist"}


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    root: Path
    project_file: Path | None
    markdown_files: tuple[Path, ...]
    docx_files: tuple[Path, ...]
    image_files: tuple[Path, ...]
    data_files: tuple[Path, ...]
    template_files: tuple[Path, ...]

    @property
    def name(self) -> str:
        return self.root.name or str(self.root)


def _files(root: Path, suffixes: set[str], *, max_files: int = 5000) -> tuple[Path, ...]:
    found: list[Path] = []
    try:
        candidates = root.rglob("*")
        for path in candidates:
            if len(found) >= max_files:
                break
            if any(part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
                continue
            if path.is_file() and path.suffix.lower() in suffixes:
                found.append(path)
    except OSError:
        pass
    return tuple(sorted(found, key=lambda p: str(p.relative_to(root)).casefold()))


def inspect_workspace(root: str | Path) -> WorkspaceSummary:
    base = Path(root).expanduser().resolve()
    project = base / "mddocx.yml"
    markdown = _files(base, _MD_SUFFIXES)
    docx = _files(base, {".docx"})
    images = _files(base, _IMAGE_SUFFIXES)
    data = _files(base, _DATA_SUFFIXES)
    templates = tuple(p for p in _files(base, _TEMPLATE_SUFFIXES) if p.suffix.lower() == ".dotx" or "template" in p.name.lower())
    return WorkspaceSummary(
        root=base,
        project_file=project if project.is_file() else None,
        markdown_files=markdown,
        docx_files=docx,
        image_files=images,
        data_files=data,
        template_files=templates,
    )


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
