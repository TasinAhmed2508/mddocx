from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
from typing import Iterable

from .compiler import Compiler
from .config import RenderConfig
from .diagnostics import Diagnostic, MddocxError
from .output import validate_output_path


@dataclass(slots=True)
class BatchResult:
    input_path: Path
    output_path: Path | None
    ok: bool
    error: str | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def recovered(self) -> bool:
        return any(item.code == "RECOVER201" for item in self.diagnostics)


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
    jobs: int = 1,
) -> list[BatchResult]:
    if not isinstance(jobs, int) or isinstance(jobs, bool) or jobs < 1:
        raise ValueError("jobs must be a positive integer")
    source_paths = collect_markdown_inputs(inputs, recursive=recursive)
    target_root = Path(output_dir)
    target_root.mkdir(parents=True, exist_ok=True)
    names: dict[str, Path] = {}
    plans: list[tuple[Path, Path]] = []
    for source in source_paths:
        base = source.stem + ".docx"
        if base.casefold() in names:
            suffix = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:8]
            base = f"{source.stem}-{suffix}.docx"
        candidate = base
        index = 2
        while candidate.casefold() in names:
            candidate = f"{Path(base).stem}-{index}.docx"
            index += 1
        names[candidate.casefold()] = source
        plans.append((source, target_root / candidate))

    def convert(plan: tuple[Path, Path]) -> BatchResult:
        source, target = plan
        previous = target.is_file()
        try:
            validate_output_path(target, source_paths)
            result = Compiler(config).compile_file(source, target)
            return BatchResult(source, target, True, diagnostics=result.diagnostics)
        except MddocxError as exc:
            message = str(exc)
            if previous:
                message += f" Previous output left in place: {target}"
            return BatchResult(source, None, False, message, (exc.diagnostic,))
        except Exception as exc:
            message = str(exc)
            if previous:
                message += f" Previous output left in place: {target}"
            return BatchResult(source, None, False, message)

    if jobs > 1 and not fail_fast and not (config and config.performance.track_memory):
        with ThreadPoolExecutor(max_workers=min(jobs, len(plans) or 1)) as pool:
            return list(pool.map(convert, plans))
    results = []
    for plan in plans:
        result = convert(plan)
        results.append(result)
        if fail_fast and not result.ok:
            break
    return results
