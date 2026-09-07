from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from mddocx import CacheConfig, CompilationLimits, MarkdownWord, RenderConfig, render_string
from mddocx.diagnostics import MddocxError


def test_reproducible_docx_has_fixed_zip_metadata_and_stable_bytes():
    markdown = "# Stable\n\nText with $x^2$ and **bold**.\n"
    a = render_string(markdown)
    b = render_string(markdown)
    assert a == b
    with ZipFile(BytesIO(a)) as archive:
        assert archive.infolist()
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
        names = archive.namelist()
        assert names == sorted(names)


def test_input_limit_is_enforced():
    converter = MarkdownWord(RenderConfig(limits=CompilationLimits(max_input_bytes=8)))
    with pytest.raises(MddocxError) as exc:
        converter.render_string("123456789")
    assert exc.value.diagnostic.code == "LIMIT401"


def test_ast_node_limit_is_enforced():
    converter = MarkdownWord(RenderConfig(limits=CompilationLimits(max_ast_nodes=3)))
    with pytest.raises(MddocxError) as exc:
        converter.render_string("# H\n\nOne\n\nTwo\n")
    assert exc.value.diagnostic.code == "LIMIT402"


def test_persistent_ast_cache_hits_on_second_compile(tmp_path: Path):
    cfg = RenderConfig(cache=CacheConfig(ast_enabled=True, directory=tmp_path / "cache"))
    first = MarkdownWord(cfg)
    first.render_string("# Cached\n\nHello **world**.\n", base_dir=tmp_path)
    assert first.last_stats.ast_cache_hit is False

    second = MarkdownWord(cfg)
    second.render_string("# Cached\n\nHello **world**.\n", base_dir=tmp_path)
    assert second.last_stats.ast_cache_hit is True
    assert any(d.code == "CACHE401" for d in second.diagnostics)
    assert list((tmp_path / "cache").glob("*.json"))
