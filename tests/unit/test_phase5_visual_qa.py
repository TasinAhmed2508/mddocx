from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from mddocx.visual_qa import compare_visual_pages, image_similarity


def _page(path: Path, mark: bool = False):
    image = Image.new("L", (120, 80), 255)
    if mark:
        ImageDraw.Draw(image).rectangle((20, 20, 80, 50), fill=0)
    image.save(path)


def test_visual_similarity_and_page_set_comparison(tmp_path: Path):
    baseline = tmp_path / "baseline"
    actual = tmp_path / "actual"
    baseline.mkdir(); actual.mkdir()
    _page(baseline / "page-1.png", mark=True)
    _page(actual / "page-1.png", mark=True)
    assert image_similarity(baseline / "page-1.png", actual / "page-1.png") == 1.0
    report = compare_visual_pages(baseline, actual, threshold=0.999)
    assert report.ok
