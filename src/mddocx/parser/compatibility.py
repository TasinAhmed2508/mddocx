from __future__ import annotations

import base64
import re

INLINE_SENTINEL = "MDDOCXMATH"


def _enc(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def decode_inline_math(value: str) -> str:
    pad = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + pad).decode("utf-8")


def normalize_math_syntax(markdown: str) -> str:
    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = markdown.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        one = re.match(r"^\$\$(.+?)\$\$\s*(\{[^{}]+\})?$", stripped)
        if one:
            out.extend(["```mddocx-math", one.group(1).strip(), "```"])
            if one.group(2): out.append(one.group(2))
            i += 1
            continue
        if stripped in {"$$", r"\["}:
            is_dollar = stripped == "$$"
            i += 1
            body: list[str] = []
            attrs = None
            while i < len(lines):
                close_match = re.match(r"^\$\$\s*(\{[^{}]+\})?$", lines[i].strip()) if is_dollar else re.match(r"^\\\]\s*(\{[^{}]+\})?$", lines[i].strip())
                if close_match:
                    attrs = close_match.group(1)
                    i += 1
                    break
                body.append(lines[i])
                i += 1
            out.extend(["```mddocx-math", "\n".join(body), "```"])
            if attrs: out.append(attrs)
            continue
        out.append(lines[i])
        i += 1

    text = "\n".join(out)
    text = re.sub(
        r"\\\((.+?)\\\)",
        lambda m: f"{INLINE_SENTINEL}{_enc(m.group(1))}ENDMATH",
        text,
        flags=re.S,
    )
    return text



def normalize_definition_lists(markdown: str) -> str:
    """Normalize common `Term` + `: definition` syntax into bounded sentinel fences."""
    lines = markdown.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if i + 1 < len(lines) and lines[i].strip() and re.match(r"^\s*:\s+", lines[i + 1]):
            pairs: list[tuple[str, str]] = []
            while i + 1 < len(lines) and lines[i].strip() and re.match(r"^\s*:\s+", lines[i + 1]):
                term = lines[i].strip()
                definition = re.sub(r"^\s*:\s+", "", lines[i + 1]).strip()
                pairs.append((term, definition))
                i += 2
                if i < len(lines) and not lines[i].strip():
                    i += 1
            out.append("```mddocx-definition")
            for term, definition in pairs:
                out.append(term.replace("\t", " ") + "\t" + definition.replace("\t", " "))
            out.append("```")
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)

def normalize_bibliography_directives(markdown: str) -> str:
    """Normalize fenced bibliography directives into a parser sentinel."""
    return re.sub(
        r"(?ms)^\s*:::\s*bibliography\s*$.*?^\s*:::\s*$",
        "```mddocx-bibliography\n```",
        markdown,
    )

def split_text_math(text: str) -> list[tuple[str, str]]:
    """Return [('text'|'math', value)] while respecting escaped dollar signs."""
    sentinel_re = re.compile(rf"{INLINE_SENTINEL}([A-Za-z0-9_-]+)ENDMATH")
    segments: list[tuple[str, str]] = []
    pos = 0
    for m in sentinel_re.finditer(text):
        if m.start() > pos:
            segments.extend(_split_dollars(text[pos:m.start()]))
        segments.append(("math", decode_inline_math(m.group(1))))
        pos = m.end()
    if pos < len(text):
        segments.extend(_split_dollars(text[pos:]))
    return [(kind, value) for kind, value in segments if value]


def _split_dollars(text: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    buf: list[str] = []
    math: list[str] = []
    in_math = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] == "$":
            (math if in_math else buf).append("$")
            i += 2
            continue
        if ch == "$":
            if in_math:
                result.append(("math", "".join(math)))
                math = []
                in_math = False
            else:
                if buf:
                    result.append(("text", "".join(buf)))
                    buf = []
                in_math = True
            i += 1
            continue
        (math if in_math else buf).append(ch)
        i += 1
    if in_math:
        buf.append("$")
        buf.extend(math)
    if buf:
        result.append(("text", "".join(buf)))
    return result


_SIMPLE_TABLE_SEPARATOR_RE = re.compile(r"^-{3,}$")


def _simple_table_spans(line: str) -> list[tuple[int, int]] | None:
    """Return fixed-width column dash spans for Pandoc/simple Markdown tables."""
    if not line.strip() or any(ch not in "- \t" for ch in line):
        return None
    spans = [(m.start(), m.end()) for m in re.finditer(r"-{3,}", line)]
    return spans if len(spans) >= 2 else None


def _simple_table_cells(line: str, starts: list[int]) -> list[str]:
    cells: list[str] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(line)
        cells.append(line[start:end].strip())
    return cells


def _merge_simple_table_lines(lines: list[str], starts: list[int]) -> list[str]:
    cols = ["" for _ in starts]
    for line in lines:
        if not line.strip():
            continue
        cells = _simple_table_cells(line, starts)
        for i, cell in enumerate(cells):
            if cell:
                cols[i] = f"{cols[i]} {cell}".strip()
    return cols


def _pipe_row(cells: list[str]) -> str:
    # Pipes are structural in GFM tables; escape literal bars from source cells.
    safe = [cell.replace("|", r"\|") for cell in cells]
    return "| " + " | ".join(safe) + " |"


def normalize_simple_tables(markdown: str) -> str:
    """Normalize common Pandoc/simple fixed-width tables into GFM pipe tables.

    This is deliberately syntax-driven rather than document-specific. It supports
    bordered Pandoc simple tables and the common header+dash-line compact form.
    """
    lines = markdown.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        # Bordered Pandoc form. The outer border is commonly one long dash run,
        # while the header separator contains one dash run per fixed-width column.
        if re.fullmatch(r"\s*-{10,}\s*", lines[i] or ""):
            header_sep = None
            header_spans = None
            for j in range(i + 2, min(len(lines), i + 8)):
                if lines[j].lstrip().startswith("#"):
                    break
                candidate = _simple_table_spans(lines[j])
                if candidate:
                    header_sep = j
                    header_spans = candidate
                    break
            if header_sep is not None and header_spans is not None:
                closing = None
                for j in range(header_sep + 1, len(lines)):
                    if re.fullmatch(r"\s*-{10,}\s*", lines[j] or ""):
                        closing = j
                        break
                    if lines[j].lstrip().startswith("#"):
                        break
                if closing is not None:
                    starts = [s for s, _ in header_spans]
                    header = _merge_simple_table_lines(lines[i + 1:header_sep], starts)
                    rows = [
                        _simple_table_cells(line, starts)
                        for line in lines[header_sep + 1:closing]
                        if line.strip()
                    ]
                    if out and out[-1].strip():
                        out.append("")
                    out.append(_pipe_row(header))
                    out.append(_pipe_row(["---"] * len(starts)))
                    out.extend(_pipe_row(row) for row in rows)
                    out.append("")
                    i = closing + 1
                    continue

        # Bordered variant whose top border itself has per-column dash groups.
        spans = _simple_table_spans(lines[i])
        if spans:
            starts = [s for s, _ in spans]
            header_sep = None
            for j in range(i + 1, min(len(lines), i + 8)):
                candidate = _simple_table_spans(lines[j])
                if candidate and len(candidate) == len(spans):
                    header_sep = j
                    break
            if header_sep is not None and header_sep > i + 1:
                closing = None
                for j in range(header_sep + 1, len(lines)):
                    candidate = _simple_table_spans(lines[j])
                    if (candidate and len(candidate) == len(spans)) or re.fullmatch(r"\s*-{10,}\s*", lines[j] or ""):
                        closing = j
                        break
                    if lines[j].lstrip().startswith("#"):
                        break
                if closing is not None:
                    header = _merge_simple_table_lines(lines[i + 1:header_sep], starts)
                    rows = [
                        _simple_table_cells(line, starts)
                        for line in lines[header_sep + 1:closing]
                        if line.strip()
                    ]
                    if out and out[-1].strip():
                        out.append("")
                    out.append(_pipe_row(header))
                    out.append(_pipe_row(["---"] * len(starts)))
                    out.extend(_pipe_row(row) for row in rows)
                    out.append("")
                    i = closing + 1
                    continue

        # Compact simple table: header line followed by 2+ dash groups.
        if i + 1 < len(lines):
            next_spans = _simple_table_spans(lines[i + 1])
            if next_spans and lines[i].strip():
                starts = [s for s, _ in next_spans]
                rows: list[list[str]] = []
                j = i + 2
                while j < len(lines) and lines[j].strip():
                    if _simple_table_spans(lines[j]) or re.fullmatch(r"\s*[-*_]{3,}\s*", lines[j]):
                        break
                    rows.append(_simple_table_cells(lines[j], starts))
                    j += 1
                if rows:
                    if out and out[-1].strip():
                        out.append("")
                    out.append(_pipe_row(_simple_table_cells(lines[i], starts)))
                    out.append(_pipe_row(["---"] * len(starts)))
                    out.extend(_pipe_row(row) for row in rows)
                    out.append("")
                    i = j
                    continue

        out.append(lines[i])
        i += 1
    return "\n".join(out)


_FOOTNOTE_DEF_RE = re.compile(r"^ {0,3}\[\^([^\]]+)\]:[ \t]*(.*)$")


def extract_footnote_definitions(markdown: str) -> tuple[str, dict[str, str]]:
    """Extract common Markdown footnote definitions without touching fenced code.

    Supports the widespread ``[^id]: text`` form plus indented continuation lines.
    Definitions are removed from the body and returned as Markdown fragments so the
    parser can convert them to the same canonical inline AST used elsewhere.
    """
    lines = markdown.split("\n")
    out: list[str] = []
    notes: dict[str, str] = {}
    i = 0
    fence: tuple[str, int] | None = None
    while i < len(lines):
        line = lines[i]
        fence_match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence_match:
            marker = fence_match.group(1)
            ch = marker[0]
            n = len(marker)
            if fence is None:
                fence = (ch, n)
            elif fence[0] == ch and n >= fence[1]:
                fence = None
            out.append(line)
            i += 1
            continue
        if fence is not None:
            out.append(line)
            i += 1
            continue

        match = _FOOTNOTE_DEF_RE.match(line)
        if not match:
            out.append(line)
            i += 1
            continue

        label = match.group(1).strip()
        body = [match.group(2)]
        i += 1
        pending_blank = False
        while i < len(lines):
            cont = lines[i]
            if not cont.strip():
                pending_blank = True
                i += 1
                continue
            if re.match(r"^(?: {4}|\t)", cont):
                if pending_blank and body and body[-1] != "":
                    body.append("")
                body.append(re.sub(r"^(?: {4}|\t)", "", cont, count=1))
                pending_blank = False
                i += 1
                continue
            break
        notes[label] = "\n".join(body).strip()
        # Preserve block separation after stripping a definition.
        if out and out[-1].strip():
            out.append("")
    return "\n".join(out), notes


def split_footnote_references(text: str) -> list[tuple[str, str]]:
    """Split plain inline text into text/reference segments."""
    protected: dict[str, str] = {}
    sentinel_re = re.compile(rf"{FOOTNOTE_ESCAPE_SENTINEL}([A-Za-z0-9_-]+)ENDNOTE")
    def keep_literal(match):
        key = f"\x00FNESC{len(protected)}\x00"
        protected[key] = f"[^{decode_inline_math(match.group(1))}]"
        return key
    text = sentinel_re.sub(keep_literal, text)
    pattern = re.compile(r"\[\^([^\]\s]+)\]")
    result: list[tuple[str, str]] = []
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            result.append(("text", text[pos:match.start()]))
        result.append(("footnote", match.group(1)))
        pos = match.end()
    if pos < len(text):
        result.append(("text", text[pos:]))
    result = result or [("text", text)]
    restored: list[tuple[str, str]] = []
    for kind, value in result:
        if kind == "text":
            for key, literal in protected.items():
                value = value.replace(key, literal)
        restored.append((kind, value))
    return restored

FOOTNOTE_ESCAPE_SENTINEL = "MDDOCXESCFOOTNOTE"


def protect_escaped_footnote_references(markdown: str) -> str:
    return re.sub(
        r"\\\[\^([^\]]+)\]",
        lambda m: f"{FOOTNOTE_ESCAPE_SENTINEL}{_enc(m.group(1))}ENDNOTE",
        markdown,
    )


def _restore_escaped_footnotes(text: str) -> str:
    pattern = re.compile(rf"{FOOTNOTE_ESCAPE_SENTINEL}([A-Za-z0-9_-]+)ENDNOTE")
    return pattern.sub(lambda m: f"[^{decode_inline_math(m.group(1))}]", text)

_CALLOUT_KINDS = {"note", "tip", "important", "warning", "caution", "example"}


def normalize_callout_containers(markdown: str) -> str:
    """Normalize ::: note/warning style containers to GitHub-style blockquotes.

    This is intentionally bounded: only known semantic callout kinds are converted,
    arbitrary container names remain untouched.
    """
    lines = markdown.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = re.match(r"^\s*:::\s*([A-Za-z][\w-]*)(?:\s+(.+?))?\s*$", lines[i])
        if not m or m.group(1).lower() not in _CALLOUT_KINDS:
            out.append(lines[i]); i += 1; continue
        kind = m.group(1).lower()
        title = (m.group(2) or "").strip()
        body: list[str] = []
        i += 1
        while i < len(lines) and not re.match(r"^\s*:::\s*$", lines[i]):
            body.append(lines[i]); i += 1
        if i < len(lines):
            i += 1
        marker = f"> [!{kind.upper()}]"
        if title:
            marker += " " + title
        out.append(marker)
        for line in body:
            out.append("> " + line if line else ">")
    return "\n".join(out)


def split_comment_markup(text: str) -> list[tuple[str, str]]:
    """Split CriticMarkup comments: ``{>>review note<<}``.

    Returns ``('text', value)`` and ``('comment', value)`` segments. Escaped
    sequences are left untouched so source authors can show the syntax literally.
    """
    result: list[tuple[str, str]] = []
    pos = 0
    pattern = re.compile(r"(?<!\\)\{>>(.+?)<<\}")
    for match in pattern.finditer(text):
        if match.start() > pos:
            result.append(("text", text[pos:match.start()]))
        result.append(("comment", match.group(1).strip()))
        pos = match.end()
    if pos < len(text):
        result.append(("text", text[pos:]))
    return result or [("text", text)]
