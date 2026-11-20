from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lxml import etree, html

from mddocx.ast.base import SourcePosition
from mddocx.ast.block import Paragraph, Table, TableCell, TableRow
from mddocx.ast.inline import (
    Emphasis,
    HardBreak,
    Image,
    InlineCode,
    Link,
    Strikethrough,
    Strong,
    Text,
)
from mddocx.diagnostics import MddocxError
from mddocx.table_grid import table_grid

if TYPE_CHECKING:
    from markdown_it.token import Token

    from .markdown import MarkdownParser

_FORMATTING = {
    "strong": Strong,
    "b": Strong,
    "em": Emphasis,
    "i": Emphasis,
    "s": Strikethrough,
    "del": Strikethrough,
}


def parse_html_table(parser: MarkdownParser, token: Token) -> Table | Paragraph:
    source = parser._pos(token)

    def position(element) -> SourcePosition:
        return SourcePosition(source.file, (source.line or 1) + (element.sourceline or 1) - 1, 1)

    def inlines(element, *, trim: bool = False) -> list:
        pos = position(element)
        nodes = [Text(text=re.sub(r"\s+", " ", element.text), source=pos)] if element.text else []
        for child in element:
            if child.tag in _FORMATTING:
                nodes.append(_FORMATTING[child.tag](children=inlines(child), source=pos))
            elif child.tag == "br":
                nodes.append(HardBreak(source=pos))
            elif child.tag == "img" and (src := child.get("src", "").strip()):
                nodes.append(
                    Image(
                        src=src,
                        alt=child.get("alt", ""),
                        title=child.get("title"),
                        source=position(child),
                    )
                )
            elif child.tag == "code" and not len(child):
                nodes.append(InlineCode(code=child.text or "", source=pos))
            elif child.tag == "a":
                href = child.get("href", "")
                if not href or not parser.md.validateLink(href):
                    raise ValueError("Unsupported hyperlink destination.")
                if child.find(".//img") is not None:
                    raise ValueError("Unsupported linked image inside a table cell.")
                nodes.append(
                    Link(href=parser.md.normalizeLink(href), children=inlines(child), source=pos)
                )
            elif child.tag in {"span", "p"}:
                if child.tag == "p" and nodes:
                    nodes.append(HardBreak(source=pos))
                nodes.extend(inlines(child))
            else:
                raise ValueError("Unsupported element inside a table cell.")
            if child.tail:
                nodes.append(Text(text=re.sub(r"\s+", " ", child.tail), source=pos))
        if trim and nodes and isinstance(nodes[0], Text):
            nodes[0].text = nodes[0].text.lstrip()
        if trim and nodes and isinstance(nodes[-1], Text):
            nodes[-1].text = nodes[-1].text.rstrip()
        return nodes

    try:
        if not re.search(r"</table\s*>\s*$", token.content, re.I):
            raise ValueError("Missing closing table tag.")
        root = html.fragment_fromstring(
            token.content, parser=html.HTMLParser(no_network=True, recover=False)
        )
        if root.tag != "table" or root.find(".//table") is not None:
            raise ValueError("Nested or invalid HTML table.")
        rows = []
        caption = None
        for group in root:
            if group.tag == "caption" and caption is None:
                if group.find(".//img") is not None:
                    raise ValueError("Unsupported image inside a table caption.")
                inlines(group)
                caption = " ".join(group.text_content().split())
                continue
            if group.tag == "colgroup" and all(col.tag == "col" for col in group):
                continue
            if group.tag not in {"thead", "tbody", "tfoot", "tr"}:
                raise ValueError("Unsupported HTML table structure.")
            for row in [group] if group.tag == "tr" else group:
                if row.tag != "tr" or any(cell.tag not in {"td", "th"} for cell in row):
                    raise ValueError("Expected HTML table rows and cells.")
                cells = []
                for cell in row:
                    align = cell.get("align", "").lower()
                    css = re.search(
                        r"(?:^|;)\s*text-align\s*:\s*(left|center|right)\s*(?:;|$)",
                        cell.get("style", ""),
                        re.I,
                    )
                    if css:
                        align = css[1].lower()
                    cells.append(
                        TableCell(
                            children=inlines(cell, trim=True),
                            alignment=align if align in {"left", "center", "right"} else None,
                            header=cell.tag == "th",
                            source=position(cell),
                            row_span=int(cell.get("rowspan", "1")),
                            column_span=int(cell.get("colspan", "1")),
                        )
                    )
                header = group.tag == "thead" or bool(cells and all(cell.header for cell in cells))
                rows.append(TableRow(cells=cells, header=header, source=position(row)))
        if not rows or not any(row.cells for row in rows):
            raise ValueError("HTML table is empty.")
        table = Table(rows=rows, caption=caption, source=source)
        table_grid(table, parser.max_table_cells)
        return table
    except MddocxError as exc:
        if exc.diagnostic.code != "TABLE402":
            raise
        message = exc.diagnostic.message
    except (ValueError, etree.LxmlError) as exc:
        message = str(exc)
    parser.reporter.warn(
        "TABLE202",
        "HTML table kept as source text. " + message,
        source.file,
        source.line,
        "Use a complete table with rectangular rows and supported cell elements.",
    )
    return Paragraph(children=[Text(text=token.content, source=source)], source=source)
