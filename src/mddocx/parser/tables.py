"""Recognize table blocks before a parser rule can discard their source cells."""

from __future__ import annotations

import re

from markdown_it.rules_block.state_block import StateBlock

_PIPE_SEPARATOR = re.compile(r":?-+:?")
_SPAN = re.compile(r"-{3,}")
_BORDER = re.compile(r"-{10,}")
_HTML_START = re.compile(r"<table(?:\s|>)", re.I)
_HTML_CLOSE = re.compile(r"</table\s*>\s*$", re.I)
_HTML_TABLE_TAG = re.compile(r"<(/?)table(?=[\s>])[^>]*>", re.I)
_BLOCK_START = re.compile(
    r"(?:#{1,6}(?:\s|$)|[>]|[-+*]\s|\d+[.)]\s|~~~|\x60{3,}|<|(?:[-*_]\s*){3,}$)"
)


def _pipe_cells(text: str) -> list[str] | None:
    cells: list[str] = []
    start = 0
    cursor = 0
    while cursor < len(text):
        char = text[cursor]
        if char == "\\" and cursor + 1 < len(text):
            cursor += 2
            continue
        if char == "\x60":
            end = cursor + 1
            while end < len(text) and text[end] == char:
                end += 1
            pattern = re.compile(r"(?<!\x60)\x60{" + str(end - cursor) + r"}(?!\x60)")
            match = pattern.search(text, end)
            cursor = match.end() if match else end
            continue
        if char == "|":
            cells.append(text[start:cursor].strip())
            start = cursor + 1
        cursor += 1
    if not cells:
        return None
    cells.append(text[start:].strip())
    if text.startswith("|"):
        cells.pop(0)
    if start == len(text) and cells:
        cells.pop()
    # GFM removes the pipe escape before handing the code span to the inline parser.
    return [re.sub(r"(\x60+)(.*?)\1", lambda m: m[0].replace(r"\|", "|"), c) for c in cells]


def table_block(state: StateBlock, start: int, end: int, silent: bool) -> bool:
    if state.is_code_block(start):
        return False

    def line(index: int) -> str:
        if state.sCount[index] < state.blkIndent or state.is_code_block(index):
            return ""
        return state.src[state.bMarks[index] + state.tShift[index] : state.eMarks[index]].rstrip()

    first = line(start)
    if _HTML_START.match(first):
        if silent:
            return False
        cursor = start
        depth = 0
        while cursor < end:
            current = line(cursor)
            if cursor > start and re.match(r"#{1,6}\s|~~~|\x60{3,}", current):
                break
            depth += sum(-1 if match[1] else 1 for match in _HTML_TABLE_TAG.finditer(current))
            cursor += 1
            if depth <= 0 and _HTML_CLOSE.search(current):
                break
        token = state.push("mddocx_html_table", "table", 0)
        token.map = [start, cursor]
        token.content = state.getLines(start, cursor, state.blkIndent, False)
        state.line = cursor
        return True
    if start + 1 >= end or not first:
        return False

    header = None if _BLOCK_START.match(first) else _pipe_cells(first)
    separator = line(start + 1)
    marks = _pipe_cells(separator) or [separator]
    if header and len(header) == len(marks) and all(_PIPE_SEPARATOR.fullmatch(m) for m in marks):
        if silent:
            return True
        rows = [(start, header)]
        cursor = start + 2
        while cursor < end:
            current = line(cursor)
            if not current or (_BLOCK_START.match(current) and not current.startswith("|")):
                break
            cells = _pipe_cells(current)
            if not cells:
                break
            # A new header plus delimiter row starts a fresh table.
            if cursor + 1 < end:
                upcoming = line(cursor + 1)
                delimiters = _pipe_cells(upcoming) or [upcoming]
                if len(cells) == len(delimiters) and all(
                    _PIPE_SEPARATOR.fullmatch(mark) for mark in delimiters
                ):
                    break
            rows.append((cursor, cells))
            cursor += 1
        alignments = [
            "center"
            if mark.startswith(":") and mark.endswith(":")
            else "right"
            if mark.endswith(":")
            else "left"
            if mark.startswith(":")
            else None
            for mark in marks
        ]
    else:
        fixed = _fixed_rows(line, start, end)
        if fixed is None:
            return False
        if silent:
            return True
        rows, cursor = fixed
        alignments = [None] * len(rows[0][1])

    token = state.push("mddocx_table", "table", 0)
    token.map = [start, cursor]
    token.meta = {"rows": rows, "alignments": alignments}
    state.line = cursor
    return True


def _dash_starts(text: str) -> list[int]:
    if not text or any(char not in "- " for char in text):
        return []
    starts = [m.start() for m in _SPAN.finditer(text)]
    return starts if len(starts) >= 2 else []


def _fixed_rows(line, start: int, end: int):
    first = line(start)
    bordered = bool(_BORDER.fullmatch(first) or _dash_starts(first))
    header_start = start + int(bordered)
    separator = header_start + 1
    while separator < min(end, header_start + (7 if bordered else 2)):
        starts = _dash_starts(line(separator))
        if starts:
            break
        if not bordered or not line(separator) or _BLOCK_START.match(line(separator)):
            return None
        separator += 1
    else:
        return None

    def split(text: str) -> list[str] | None:
        if not text or _BLOCK_START.match(text):
            return None
        if any(index < len(text) and not text[index - 1].isspace() for index in starts[1:]):
            return None
        return [text[a:b].strip() for a, b in zip(starts, [*starts[1:], len(text)])]

    headers = [split(line(i)) for i in range(header_start, separator)]
    if not headers or any(row is None for row in headers):
        return None
    header = [" ".join(cell for cell in column if cell) for column in zip(*headers)]
    if any(not cell for cell in header):
        return None
    rows = [(header_start, header)]
    cursor = separator + 1
    while cursor < end:
        text = line(cursor)
        if bordered and (_BORDER.fullmatch(text) or _dash_starts(text) == starts):
            return (rows, cursor + 1) if len(rows) > 1 else None
        cells = split(text)
        if cells is None or not any(cells[1:]):
            break
        rows.append((cursor, cells))
        cursor += 1
    return (rows, cursor) if not bordered and len(rows) > 1 else None
