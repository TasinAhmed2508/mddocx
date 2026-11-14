"""Adversarial input corpus: hostile Markdown must degrade, never explode.

The contract this file pins down is narrow and deliberately absolute:

* ``render_string`` either returns a DOCX or raises ``MddocxError``. No other
  exception type may reach a caller, and no case may raise a bare Python error.
* Anything it does return is a readable package whose XML parts parse.

Both halves were real defects. Malformed YAML front matter escaped as a raw
PyYAML traceback and a lone surrogate escaped as ``UnicodeEncodeError``; the
cases below are the ones that caught them, kept because the failure modes are
class-level rather than line-level.

The two scale cases (``hostile_wide_table``, ``many_paragraphs``) run at a
fraction of the size used during the audit so the suite stays fast; the
full-scale versions belong to the nightly stress job in ``docs/ROADMAP.md``.
"""

from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from lxml import etree
import pytest

from mddocx import RenderConfig, render_string
from mddocx.diagnostics import MddocxError

CASES: dict[str, str] = {
    "empty": "",
    "whitespace_only": "   \n\t\n \n",
    "nul_bytes": "before\x00after\n\n# Head\x00ing\n",
    "control_chars": "a\x01b\x02c\x07d\x08e\x0bf\x0cg\n",
    "lone_surrogate": "text \ud800 end\n",
    "bom_prefix": "\ufeff# Title\n\nBody\n",
    "crlf_mixed": "# T\r\n\r\npara\r\n\r\n- a\r\n- b\r\n",
    "no_trailing_newline": "# T\npara\n- item",
    "deep_blockquote": ">" * 400 + " deep\n",
    "deep_list_nest": "".join("  " * i + "- level\n" for i in range(120)),
    "deep_emphasis": "*" * 200 + "x" + "*" * 200 + "\n",
    "unclosed_fence": "# T\n\n```python\ndef f():\n    return 1\n",
    "unclosed_math_inline": "text \\(x^2 no close\n",
    "unclosed_math_display": "\\[a+b\n\ntail\n",
    "unclosed_dollar": "cost $5 and $10 total\n\nmath $x^2\n",
    "ragged_table": "| a | b | c |\n| --- | --- |\n| 1 |\n| 1 | 2 | 3 | 4 |\n",
    "table_no_body": "| a | b |\n| --- | --- |\n",
    "hostile_wide_table": (
        "| " + " | ".join(f"c{i}" for i in range(200)) + " |\n"
        "| " + " | ".join("---" for _ in range(200)) + " |\n"
        "| " + " | ".join("v" for _ in range(200)) + " |\n"
    ),
    "adjacent_tables": "| a | b |\n| --- | --- |\n| 1 | 2 |\n\n| x |\n| --- |\n| y |\n",
    "bad_front_matter": "---\ntitle: [unclosed\n  bad: : indent\n---\n\n# T\n",
    "front_matter_not_mapping": "---\n- just\n- a\n- list\n---\n\n# T\n",
    "front_matter_unclosed": "---\ntitle: T\n\n# Heading\n",
    "front_matter_non_scalar_types": "---\nkey: !!python/object/apply:os.system ['echo hi']\n---\n\nbody\n",
    "html_block": "<div class='x'>\n<b>raw</b>\n</div>\n\n<script>alert(1)</script>\n",
    "html_comment": "<!-- comment -->\n\n# T\n",
    "footnote_undefined_ref": "text[^missing]\n",
    "footnote_duplicate": "a[^1] b[^1]\n\n[^1]: note\n",
    "footnote_orphan_def": "[^1]: orphan\n\nbody\n",
    "bad_image_path": "![alt](does-not-exist.png)\n",
    "bad_data_uri": "![alt](data:image/png;base64,!!!!notbase64!!!!)\n",
    "data_uri_truncated": "![alt](data:image/png;base64,iVBORw0KGgo)\n",
    "unreachable_image": "![alt](https://127.0.0.1:1/none.png)\n",
    "undefined_reference_link": "see [ref][nope]\n",
    "mermaid_broken": "```mermaid\ngraph TD\n  A --> \n  --> B\n```\n",
    "mermaid_large": "```mermaid\ngraph TD\n"
    + "".join(f"  n{i} --> n{i + 1}\n" for i in range(300))
    + "```\n",
    "bangla_mixed": "বাংলা লেখা with English 123\n\n# শিরোনাম\n\n| ক | খ |\n| --- | --- |\n| ১ | ২ |\n",
    "arabic_rtl": "# عنوان\n\nنص عربي طويل متصل\n\n- عنصر\n",
    "cjk_mixed": "中文文本 with English\n\n# 見出し\n",
    "emoji_astral": "hi \U0001f600 \U0001f1e7\U0001f1e9 family \U0001f468\u200d\U0001f469\u200d\U0001f467\n",
    "combining_marks": "e\u0301a\u0300\u0301\u0302 x\u0305\u0306\n",
    "rtl_ltr_mixing": "عربى English عربى English عربى\n",
    "long_single_line": "word " * 20000 + "\n",
    "many_headings": "".join(f"{'#' * ((i % 6) + 1)} H{i}\n\n" for i in range(500)),
    "setext_weird": "Title\n===\n\nSub\n---\n\n===\n",
    "attribute_syntax": "# T {#id .cls key=val}\n\nbody{.x}\n",
    "task_list_edge": "- [ ] a\n- [x] b\n- [ ]\n- [~] c\n",
    "list_start_weird": "5. five\n6. six\n\n0. zero\n\n-1. neg\n",
    "loose_tight_lists": "- a\n\n- b\n\n\n- c\n\n1. x\n\n2. y\n",
    "blockquote_nested_list": "> - a\n>   - b\n> \n>     code\n",
    "definition_list": "term\n: definition one\n: definition two\n\nother\n: def\n",
    "callout": "> [!NOTE]\n> body\n\n> [!WARNING] no space\n",
    "math_garbage": "$$\\frac{}{\\undefinedcmd{}{}$$ $\\notacommand{x}$\n",
    "math_deep": "$$" + "{" * 200 + "x" + "}" * 200 + "$$\n",
    "equation_numbered": "$$\nx = 1\n$$ {#eq:one}\n\nSee @eq:one.\n",
    "chart_without_series": '```chart\n{"type": "bar"}\n```\n',
    "chart_bad_yaml": "```chart\n{not json at all\n```\n",
    "datatable_bad": "```data-table\nnope.csv\n```\n",
    "csv_block": "```csv\na,b\n1,2\n```\n",
    "json_block_broken": '```json-data\n{"a": [1,2,}\n```\n',
    "page_break_many": "\\newpage\n" * 100,
    "horizontal_rules": "---\n\n***\n\n___\n\n- - -\n",
    "citation_missing_key": "Text [@nosuchkey2020].\n",
    "toc_many": "\\tableofcontents\n\n" + "".join(f"## S{i}\n\ntext\n\n" for i in range(200)),
    "only_bracket_noise": "!!! ??? ***\n",
    "backslash_soup": "\\\\ \\* \\_ \\` \\[ \\] \\( \\) \\< \\> \\\\*\n",
    "entity_soup": "&amp; &lt; &gt; &nbsp; &unknown; &#xFFFF; &#0;\n",
    "xml_illegal_codepoints": "text \ufffe \uffff \x0e\x0f here\n",
    "literal_surrogate_escape": "\\uD83D\\uDE00 literal escapes\n",
    "very_long_word": "x" * 50000 + "\n",
    "many_links": " ".join(f"[l{i}](https://e.com/{i})" for i in range(500)) + "\n",
    "nested_links": "[a [b [c](x)](y)](z)\n",
    "nested_images": "![a ![b](x.png)](y.png)\n",
    "autolink_weird": "<https://e.com/a b> <mailto:> <>\n",
    "heading_no_space": "#NoSpace\n##Also\n",
    "table_escaped_pipe": "| a \\| b | c |\n| --- | --- |\n| 1 | 2 |\n",
    "code_fence_attributes": "```{.python .numberLines}\nx = 1\n```\n",
    "math_in_code_span": "use `$x$` and `\\(y\\)` in code\n",
    "typographic_extensions": "HTML and ==mark== and ++ins++ and ^sup^ and ~sub~\n",
    "wiki_links": "[[Wiki Page]] [[Target|Label]]\n",
    "deep_nested_blockquotes": "".join(">" * i + " level\n\n" for i in range(1, 60)),
    "tab_indented_code": "\tcode\n\tmore\n\n- \titem\n",
    "empty_headings": "#\n\n##\n\n### \n",
    "only_delimiters": "***\n\n___\n\n+++\n\n!!!\n",
    "mixed_line_endings": "a\r\nb\nc\rd\n",
    "control_char_in_table": "| a | b |\n| --- | --- |\n| \x00 | 2 |\n",
    "many_paragraphs": "para\n\n" * 2000,
    "adjacent_math_blocks": "$$\n$$ $$\n$$\n\n$x$ $y$ $z$\n",
    "front_matter_all_keys": (
        "---\n"
        "title: T\nauthor: A\ntheme: academic\ntoc: true\npage_numbers: true\n"
        "header: H\nfooter: F\ntemplate: missing.docx\nfonts:\n  bengali: Nope\n"
        "rtl: force\nlimits:\n  max_input_chars: 10\n---\n\n# Body\n"
    ),
    "zero_width_only": "\u200b\u200c\u200d\ufeff\n",
    "label": "\u2018\u2019\u201c\u201d\u2013\u2014\u2026\u00a0\n",
}

_REQUIRED_PARTS = ("[Content_Types].xml", "_rels/.rels", "word/document.xml")


def _assert_readable_package(blob: bytes) -> None:
    with ZipFile(BytesIO(blob)) as package:
        assert package.testzip() is None
        names = set(package.namelist())
        for required in _REQUIRED_PARTS:
            assert required in names, f"missing {required}"
        for name in names:
            if name.endswith((".xml", ".rels")):
                etree.fromstring(package.read(name))


@pytest.mark.parametrize("case", sorted(CASES))
def test_hostile_input_degrades_instead_of_raising(case: str) -> None:
    try:
        blob = render_string(CASES[case], config=RenderConfig())
    except MddocxError:
        return
    _assert_readable_package(blob)
