from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_MD_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
_DATA_SUFFIXES = {".csv", ".json"}
_TEMPLATE_SUFFIXES = {".docx", ".dotx"}


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


def list_workspace_files(root: Path) -> tuple[Path, ...]:
    found: list[Path] = []
    try:
        for path in root.iterdir():
            try:
                if path.is_file() and path.resolve().parent == root:
                    found.append(path)
            except (OSError, RuntimeError):
                continue
    except OSError:
        pass
    return tuple(sorted(found, key=lambda p: (p.name.casefold(), p.name)))


def inspect_workspace(root: str | Path) -> WorkspaceSummary:
    base = Path(root).expanduser().resolve()
    project = base / "mddocx.yml"
    files = list_workspace_files(base)
    markdown = tuple(p for p in files if p.suffix.lower() in _MD_SUFFIXES)
    docx = tuple(p for p in files if p.suffix.lower() == ".docx")
    images = tuple(p for p in files if p.suffix.lower() in _IMAGE_SUFFIXES)
    data = tuple(p for p in files if p.suffix.lower() in _DATA_SUFFIXES)
    templates = tuple(
        p
        for p in files
        if p.suffix.lower() in _TEMPLATE_SUFFIXES
        and (p.suffix.lower() == ".dotx" or "template" in p.name.lower())
    )
    return WorkspaceSummary(
        root=base,
        project_file=project if project in files else None,
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
