from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from time import perf_counter

from .api import MarkdownWord
from .config import PerformanceConfig, RenderConfig
from .inspection import inspect_docx_bytes


@dataclass(slots=True)
class BenchmarkReport:
    sections: int
    markdown_bytes: int
    output_bytes: int
    elapsed_seconds: float
    peak_memory_bytes: int | None
    paragraphs: int
    equations: int
    tables: int
    sha256: str
    max_seconds: float
    max_peak_memory_bytes: int | None
    structural_ok: bool

    @property
    def time_ok(self) -> bool:
        return self.elapsed_seconds <= self.max_seconds

    @property
    def memory_ok(self) -> bool:
        return (
            self.max_peak_memory_bytes is None
            or self.peak_memory_bytes is None
            or self.peak_memory_bytes <= self.max_peak_memory_bytes
        )

    @property
    def ok(self) -> bool:
        return self.structural_ok and self.time_ok and self.memory_ok

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload.update({"time_ok": self.time_ok, "memory_ok": self.memory_ok, "ok": self.ok})
        return payload

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, sort_keys=True)

    def to_text(self) -> str:
        peak = (
            "n/a"
            if self.peak_memory_bytes is None
            else f"{self.peak_memory_bytes / 1024 / 1024:.1f} MiB"
        )
        return "\n".join(
            [
                f"mddocx performance gate: {'PASS' if self.ok else 'FAIL'}",
                f"Sections: {self.sections}",
                f"Markdown: {self.markdown_bytes} bytes  DOCX: {self.output_bytes} bytes",
                f"Elapsed: {self.elapsed_seconds:.3f}s / {self.max_seconds:.3f}s",
                f"Peak traced Python memory: {peak}",
                f"Paragraphs/equations/tables: {self.paragraphs}/{self.equations}/{self.tables}",
                f"Structural inspection: {'PASS' if self.structural_ok else 'FAIL'}",
                f"SHA-256: {self.sha256}",
            ]
        )


def build_benchmark_markdown(sections: int = 100) -> str:
    sections = max(1, int(sections))
    parts = ["# Large-document benchmark", "", "Generated deterministically by mddocx.", ""]
    for idx in range(1, sections + 1):
        parts.extend(
            [
                f"## Section {idx}",
                "",
                "This paragraph contains **bold**, *italic*, a [link](https://example.com), and inline math $E=mc^2$.",
                "",
                "- First item",
                "  - Nested item",
                "- Final item",
                "",
                "$$",
                rf"\sum_{{i=1}}^{{{idx + 3}}} i = \frac{{({idx + 3})({idx + 4})}}{{2}}",
                "$$",
                "",
                "| Metric | Value |",
                "|---|---:|",
                f"| Section | {idx} |",
                f"| Square | {idx * idx} |",
                "",
            ]
        )
    return "\n".join(parts)


def run_performance_gate(
    *,
    sections: int = 100,
    max_seconds: float = 15.0,
    max_peak_memory_bytes: int | None = 512 * 1024 * 1024,
) -> BenchmarkReport:
    markdown = build_benchmark_markdown(sections)
    config = RenderConfig(
        title="mddocx performance gate",
        performance=PerformanceConfig(enabled=True, track_memory=True),
    )
    converter = MarkdownWord(config)
    started = perf_counter()
    blob = converter.render_string(markdown)
    elapsed = perf_counter() - started
    inspection = inspect_docx_bytes(blob)
    return BenchmarkReport(
        sections=max(1, int(sections)),
        markdown_bytes=len(markdown.encode("utf-8")),
        output_bytes=len(blob),
        elapsed_seconds=elapsed,
        peak_memory_bytes=converter.last_stats.peak_memory_bytes,
        paragraphs=inspection.paragraphs,
        equations=inspection.equations,
        tables=inspection.tables,
        sha256=converter.last_stats.output_sha256 or "",
        max_seconds=float(max_seconds),
        max_peak_memory_bytes=max_peak_memory_bytes,
        structural_ok=inspection.ok,
    )
