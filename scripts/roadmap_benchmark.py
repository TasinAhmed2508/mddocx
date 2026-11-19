"""Run identical workloads with PYTHONPATH pointed at each candidate's src."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc
from unittest.mock import patch

from mddocx import MarkdownWord, build_project
from mddocx.benchmark import build_benchmark_markdown
from mddocx.math.converter import DefaultMathConverter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--only", action="append", help="Run a named workload, repeatable")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")

    width = 24
    table = "\n".join(
        "|" + "|".join(row) + "|"
        for row in [["Header"] * width, ["---"] * width]
        + [[f"cell {r},{c}" for c in range(width)] for r in range(60)]
    )
    diagram = "flowchart TD\n" + "\n".join(
        f"N{i}[Step {i}] -->|next| N{i + 1}[Step {i + 1}]" for i in range(60)
    )
    workloads = {
        "mixed": build_benchmark_markdown(20),
        "wide_table": table,
        "unique_math": "\n\n".join(f"Equation $x^{i}+1$." for i in range(1, 21)),
        "repeated_math": "\n\n".join(["Equation $x^2+1$."] * 40),
        "package_parts": (
            "Claim.[^note]\n\n[^note]: A native note.\n\n"
            + "\n\n".join(
                "~~~chart\ncategories: [A, B]\nseries: {Count: [1, 2]}\n~~~" for _ in range(4)
            )
        ),
        "mermaid": f"```mermaid\n{diagram}\n```",
    }
    report = {}
    with TemporaryDirectory() as directory:
        root = Path(directory)
        includes = []
        for index in range(8):
            name = f"chapter-{index}.md"
            (root / name).write_text(f"## Chapter {index}\n\nLocal data.", encoding="utf-8")
            includes.append(f"@include {name}")
        (root / "main.md").write_text("# Project\n\n" + "\n\n".join(includes), encoding="utf-8")
        (root / "mddocx.yml").write_text("version: 1\nsources: [main.md]\n", encoding="utf-8")

        for name in (*workloads, "project_includes"):
            if args.only and name not in args.only:
                continue
            engines: Counter[str] = Counter()

            class Converter(DefaultMathConverter):
                def convert(self, latex, display=False):
                    result = super().convert(latex, display)
                    engines[result.engine] += 1
                    return result

            timings, peaks, hashes = [], [], set()
            for index in range(args.runs + 1):
                if index == args.runs:
                    tracemalloc.start()
                start = perf_counter()
                with patch("mddocx.render.renderer.DefaultMathConverter", Converter):
                    if name == "project_includes":
                        blob = build_project(root, force=True).output_path.read_bytes()
                    else:
                        blob = MarkdownWord().render_string(workloads[name])
                elapsed = perf_counter() - start
                if index == args.runs:
                    peaks.append(tracemalloc.get_traced_memory()[1])
                    tracemalloc.stop()
                else:
                    timings.append(elapsed)
                hashes.add(sha256(blob).hexdigest())
            assert len(hashes) == 1, f"Nondeterministic output for {name}"
            report[name] = {
                "median_seconds": round(median(timings), 4),
                "peak_python_bytes": max(peaks),
                "output_bytes": len(blob),
                "engines": sorted(engines),
                "sha256": hashes.pop(),
            }
            print(json.dumps({name: report[name]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
