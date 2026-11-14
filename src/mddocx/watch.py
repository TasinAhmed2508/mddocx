from __future__ import annotations

from pathlib import Path
from time import sleep
from typing import Callable

from .compiler import CompilationResult, Compiler
from .diagnostics import MddocxError


def watch_file(
    source: Path,
    output: Path,
    *,
    interval: float,
    once: bool,
    on_build: Callable[[CompilationResult], None],
    on_error: Callable[[Exception], None],
) -> None:
    """Poll the source and local dependencies, rebuilding after a stable sample."""
    compiler = Compiler()
    dependencies = {source.resolve()}

    def snapshot():
        result = {}
        for path in dependencies:
            try:
                stat = path.stat()
                result[path] = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                result[path] = None
        return result

    pending = None
    previous = snapshot()
    while True:
        try:
            result = compiler.compile_file(source, output)
        except (MddocxError, OSError, ValueError) as exc:
            if once:
                raise
            on_error(exc)
        else:
            new_dependencies = set(result.dependencies) - {output.resolve()}
            dependencies = {source.resolve(), *new_dependencies}
            current = snapshot()
            previous = {path: previous.get(path, value) for path, value in current.items()}
            on_build(result)
        if once:
            return
        while True:
            sleep(interval)
            current = snapshot()
            if current == previous:
                pending = None
            elif current == pending:
                previous, pending = current, None
                break
            else:
                pending = current
