from __future__ import annotations

import json

from mddocx.bibliography import BibliographyDatabase, BibliographyEntry, canonical_doi
from mddocx.linkcheck import LinkChecker, collect_links, results_json


def test_doi_normalization_and_invalid_values():
    expected = "https://doi.org/10.1000/xyz"
    assert canonical_doi("10.1000/xyz") == expected
    assert canonical_doi("doi:10.1000/xyz.") == expected
    assert canonical_doi("https://doi.org/10.1000/xyz") == expected
    assert canonical_doi("not a doi") == ""


def test_numeric_citations_follow_first_citation_order_and_filter_entries():
    database = BibliographyDatabase(
        {
            "a": BibliographyEntry("a", "Alpha", ["Able, A"], "2020"),
            "b": BibliographyEntry("b", "Beta", ["Baker, B"], "2021"),
        }
    )
    assert database.cite(["b"], "ieee") == "[1]"
    assert database.cite(["a", "b"], "ieee") == "[2, 1]"
    assert [key for key, _ in database.formatted_segments("ieee", ["b"])] == ["b"]


def test_bibliography_segments_make_doi_hyperlink_ready():
    database = BibliographyDatabase(
        {
            "paper": BibliographyEntry(
                "paper", "A paper", ["Doe, Jane"], "2024", doi="doi:10.1/no"
            ),
            "valid": BibliographyEntry("valid", "Valid", ["Doe, Jane"], "2024", doi="10.1000/xyz"),
        }
    )
    _, segments = database.formatted_segments("apa", ["valid"])[0]
    assert segments[-1].href == "https://doi.org/10.1000/xyz"
    assert any("CITE204" in item for item in database.diagnostics)


def test_link_collection_excludes_markdown_images_and_includes_bibliography():
    database = BibliographyDatabase({"r": BibliographyEntry("r", doi="10.1000/ref")})
    markdown = (
        "[paper](https://example.test/p) ![plot](https://example.test/i.png) <https://x.test>"
    )
    assert collect_links(markdown, database) == [
        "https://example.test/p",
        "https://x.test",
        "https://doi.org/10.1000/ref",
    ]


def test_link_checker_offline_and_json_output():
    result = LinkChecker(offline=True).check("https://example.test")
    assert result.status == "skipped"
    assert json.loads(results_json([result]))[0]["broken"] is False


def test_malformed_link_is_confirmed_broken():
    result = LinkChecker().check("ftp://example.test")
    assert result.status == "malformed"
    assert result.broken


def test_local_csl_style_changes_citation_and_bibliography_rendering(tmp_path):
    style = tmp_path / "custom.csl"
    style.write_text(
        '<style xmlns="http://purl.org/net/xbiblio/csl" version="1.0" class="in-text">'
        "<info><title>Laboratory Style</title><id>https://example.test/lab</id>"
        "<updated>2026-01-01T00:00:00+00:00</updated></info>"
        '<citation><layout prefix="CITE[" suffix="]"><text variable="title" '
        'text-case="uppercase"/></layout></citation>'
        '<bibliography><layout prefix="CUSTOM: "><text variable="title" '
        'text-case="uppercase"/></layout></bibliography></style>',
        encoding="utf-8",
    )
    database = BibliographyDatabase({"paper": BibliographyEntry("paper", "Novel result")})
    selected = database.resolve_style("apa", style)
    assert selected == "csl-local"
    assert database.cite(["paper"], selected) == "CITE[NOVEL RESULT]"
    assert database.formatted_entries(selected, ["paper"]) == [("paper", "CUSTOM: NOVEL RESULT")]
    assert database.diagnostics == []


def test_unsupported_local_csl_style_emits_diagnostic(tmp_path):
    style = tmp_path / "custom.csl"
    style.write_text("<not-a-style />", encoding="utf-8")
    database = BibliographyDatabase()
    assert database.resolve_style("apa", style) == "apa"
    assert any("CITE205" in message for message in database.diagnostics)
