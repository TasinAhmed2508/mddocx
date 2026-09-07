import json
from pathlib import Path
import pytest

from mddocx.bibliography import BibliographyDatabase


BIB = '''
@article{smith2025,
 author={Smith, Jane and Doe, John},
 title={Native Word Rendering},
 year={2025},
 journal={Document Systems}
}
@book{jones2024,
 author={Jones, Alex},
 title={Document Compilers},
 year={2024},
 publisher={Example Press}
}
'''


def test_bibtex_load(tmp_path):
    path = tmp_path / "refs.bib"; path.write_text(BIB)
    db = BibliographyDatabase.load(path)
    assert set(db.entries) == {"smith2025", "jones2024"}
    assert db.entries["smith2025"].year == "2025"


def test_author_year_citation(tmp_path):
    path = tmp_path / "refs.bib"; path.write_text(BIB)
    db = BibliographyDatabase.load(path)
    assert db.cite(["smith2025"], "author-year") == "(Smith & Doe, 2025)"


def test_citation_suffix(tmp_path):
    path = tmp_path / "refs.bib"; path.write_text(BIB)
    db = BibliographyDatabase.load(path)
    assert "p. 42" in db.cite(["smith2025"], "apa", "p. 42")


def test_numeric_citation(tmp_path):
    path = tmp_path / "refs.bib"; path.write_text(BIB)
    db = BibliographyDatabase.load(path)
    assert db.cite(["jones2024"], "ieee") == "[2]"


def test_bibliography_entry_format(tmp_path):
    path = tmp_path / "refs.bib"; path.write_text(BIB)
    db = BibliographyDatabase.load(path)
    rendered = dict(db.formatted_entries())
    assert "Native Word Rendering" in rendered["smith2025"]


def test_csl_json_load(tmp_path):
    data = [{"id":"csl1","title":"CSL Entry","author":[{"family":"Lee","given":"Ada"}],"issued":{"date-parts":[[2026]]}}]
    path = tmp_path / "refs.json"; path.write_text(json.dumps(data))
    db = BibliographyDatabase.load(path)
    assert db.entries["csl1"].author_short == "Lee"
    assert db.entries["csl1"].year == "2026"


@pytest.mark.parametrize("style", ["author-year", "apa", "ieee", "numeric"])
def test_supported_styles_do_not_crash(tmp_path, style):
    path = tmp_path / "refs.bib"; path.write_text(BIB)
    db = BibliographyDatabase.load(path)
    assert db.cite(["smith2025"], style)
