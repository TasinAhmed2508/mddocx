from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageChops, ImageStat


class VisualQAUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class PageComparison:
    page: int
    similarity: float
    baseline: str
    actual: str


@dataclass(slots=True)
class VisualQAReport:
    page_count: int
    threshold: float
    comparisons: list[PageComparison] = field(default_factory=list)
    missing_baseline_pages: list[int] = field(default_factory=list)
    extra_baseline_pages: list[int] = field(default_factory=list)

    @property
    def min_similarity(self) -> float:
        return min((item.similarity for item in self.comparisons), default=0.0 if self.page_count else 1.0)

    @property
    def ok(self) -> bool:
        return (
            not self.missing_baseline_pages
            and not self.extra_baseline_pages
            and self.page_count == len(self.comparisons)
            and all(item.similarity >= self.threshold for item in self.comparisons)
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "page_count": self.page_count,
            "threshold": self.threshold,
            "min_similarity": self.min_similarity,
            "ok": self.ok,
            "missing_baseline_pages": self.missing_baseline_pages,
            "extra_baseline_pages": self.extra_baseline_pages,
            "comparisons": [asdict(item) for item in self.comparisons],
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def to_text(self) -> str:
        lines = [
            f"mddocx visual QA: {'PASS' if self.ok else 'DIFF'}",
            f"Pages: {self.page_count}",
            f"Threshold: {self.threshold:.4f}",
            f"Minimum similarity: {self.min_similarity:.4f}",
        ]
        for item in self.comparisons:
            status = "PASS" if item.similarity >= self.threshold else "DIFF"
            lines.append(f"  page {item.page}: {item.similarity:.4f} {status}")
        if self.missing_baseline_pages:
            lines.append("Missing baseline pages: " + ", ".join(map(str, self.missing_baseline_pages)))
        if self.extra_baseline_pages:
            lines.append("Extra baseline pages: " + ", ".join(map(str, self.extra_baseline_pages)))
        return "\n".join(lines)


def render_docx_pages(docx_path: str | Path, output_dir: str | Path, dpi: int = 144) -> list[Path]:
    docx_path = Path(docx_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    office = shutil.which("libreoffice") or shutil.which("soffice")
    pdftoppm = shutil.which("pdftoppm")
    if not office or not pdftoppm:
        raise VisualQAUnavailable("Visual QA requires LibreOffice/soffice and pdftoppm.")

    with tempfile.TemporaryDirectory(prefix="mddocx-visual-") as tmp:
        tmp_path = Path(tmp)
        profile = tmp_path / "lo-profile"
        home = tmp_path / "home"
        profile.mkdir()
        home.mkdir()
        env = os.environ.copy()
        env["HOME"] = str(home)
        cmd = [
            office,
            "--headless",
            f"-env:UserInstallation={profile.as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmp_path),
            str(docx_path),
        ]
        completed = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        pdf = tmp_path / (docx_path.stem + ".pdf")
        if completed.returncode != 0 or not pdf.is_file():
            detail = (completed.stderr or completed.stdout or "LibreOffice conversion failed").strip()
            raise VisualQAUnavailable(detail)
        prefix = output_dir / "page"
        completed = subprocess.run(
            [pdftoppm, "-png", "-r", str(dpi), str(pdf), str(prefix)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0:
            raise VisualQAUnavailable((completed.stderr or "pdftoppm failed").strip())
    return _sorted_pages(output_dir)


def compare_visual_pages(baseline_dir: str | Path, actual_dir: str | Path, threshold: float = 0.985) -> VisualQAReport:
    baseline = _sorted_pages(Path(baseline_dir))
    actual = _sorted_pages(Path(actual_dir))
    baseline_map = {_page_number(path): path for path in baseline}
    actual_map = {_page_number(path): path for path in actual}
    comparisons: list[PageComparison] = []
    for page in sorted(set(baseline_map).intersection(actual_map)):
        score = image_similarity(baseline_map[page], actual_map[page])
        comparisons.append(PageComparison(page, score, str(baseline_map[page]), str(actual_map[page])))
    return VisualQAReport(
        page_count=len(actual),
        threshold=threshold,
        comparisons=comparisons,
        missing_baseline_pages=sorted(set(actual_map).difference(baseline_map)),
        extra_baseline_pages=sorted(set(baseline_map).difference(actual_map)),
    )


def image_similarity(first: str | Path, second: str | Path) -> float:
    with Image.open(first) as a_raw, Image.open(second) as b_raw:
        a = a_raw.convert("L")
        b = b_raw.convert("L")
        if a.size != b.size:
            return 0.0
        diff = ImageChops.difference(a, b)
        # Mean absolute pixel difference mapped to [0, 1]. This deliberately
        # tolerates small anti-aliasing differences while reacting strongly to
        # shifted/missing equations, list markers, tables or page reflow.
        mean = ImageStat.Stat(diff).mean[0]
        return max(0.0, 1.0 - mean / 255.0)


def update_visual_baseline(actual_dir: str | Path, baseline_dir: str | Path) -> list[Path]:
    actual = _sorted_pages(Path(actual_dir))
    baseline_dir = Path(baseline_dir)
    if baseline_dir.exists():
        for old in baseline_dir.glob("page-*.png"):
            old.unlink()
    baseline_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for path in actual:
        target = baseline_dir / path.name
        shutil.copy2(path, target)
        out.append(target)
    return out


def _sorted_pages(directory: Path) -> list[Path]:
    return sorted(directory.glob("page-*.png"), key=_page_number)


def _page_number(path: Path) -> int:
    try:
        return int(path.stem.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 0
