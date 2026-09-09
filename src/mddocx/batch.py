from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable

from .compiler import Compiler
from .config import RenderConfig
from .diagnostics import Diagnostic, MddocxError


@dataclass(slots=True)
class BatchResult:
    input_path: Path
    output_path: Path | None
    ok: bool
    error: str | None = None
    diagnostics: tuple[Diagnostic, ...] = ()


def collect_markdown_inputs(paths: Iterable[str | Path], recursive: bool = False) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            pattern = "**/*.md" if recursive else "*.md"
            found.extend(p for p in path.glob(pattern) if p.is_file())
        elif path.is_file():
            found.append(path)
        else:
            raise FileNotFoundError(path)
    return sorted(dict.fromkeys(p.resolve() for p in found), key=lambda p: str(p).casefold())


def render_many(
    inputs: Iterable[str | Path],
    output_dir: str | Path,
    config: RenderConfig | None = None,
    *,
    recursive: bool = False,
    fail_fast: bool = False,
) -> list[BatchResult]:
    source_paths = collect_markdown_inputs(inputs, recursive=recursive)
    target_root = Path(output_dir)
    target_root.mkdir(parents=True, exist_ok=True)
    names: dict[str, Path] = {}
    results: list[BatchResult] = []
    for source in source_paths:
        base = source.stem + ".docx"
        if base.casefold() in names:
            suffix = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:8]
            base = f"{source.stem}-{suffix}.docx"
        names[base.casefold()] = source
        target = target_root / base
        compiler = Compiler(config)
        try:
            result = compiler.compile_file(source, target)
            results.append(BatchResult(source, target, True, diagnostics=result.diagnostics))
        except MddocxError as exc:
            results.append(BatchResult(source, None, False, str(exc), (exc.diagnostic,)))
            if fail_fast:
                break
        except Exception as exc:
            results.append(BatchResult(source, None, False, str(exc)))
            if fail_fast:
                break
    return results
