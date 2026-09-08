from __future__ import annotations

import base64
from dataclasses import dataclass
import re

INLINE_SENTINEL = "MDDOCXMATH"


@dataclass(frozen=True, slots=True)
class MathSyntaxIssue:
    line: int
    message: str


def find_math_syntax_issues(markdown: str) -> list[MathSyntaxIssue]:
    """Find high-confidence unterminated AI/MathJax math delimiters.

    The check deliberately ignores ordinary fenced code and ambiguous lone
    dollar signs. Its purpose is to explain why an explicit display delimiter,
    ``\\(...\\)`` pair, or math-labelled fence was preserved as source text.
    """
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    issues: list[MathSyntaxIssue] = []
    fence: tuple[str, int, bool, int] | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is not None:
            char, size, is_math, opened_at = fence
            closes = bool(
                match
                and match.group(1)[0] == char
                and len(match.group(1)) >= size
                and not match.group(2).strip()
            )
            if closes:
                fence = None
            elif i == len(lines) - 1 and is_math:
                issues.append(
                    MathSyntaxIssue(opened_at, "Unterminated math-labelled fenced block.")
                )
            i += 1
            continue
        if match:
            marker, raw_info = match.groups()
            info = raw_info.strip().split(None, 1)[0].lower() if raw_info.strip() else ""
            fence = (
                marker[0],
                len(marker),
                info in {"math", "latex", "tex", "mddocx-math"},
                i + 1,
            )
            i += 1
            continue

        stripped = line.strip()
        if stripped in {"$$", r"\["}:
            close_re = (
                re.compile(r"^\$\$\s*(?:\{[^{}]+\})?$")
                if stripped == "$$"
                else re.compile(r"^\\\]\s*(?:\{[^{}]+\})?$")
            )
            closing = next(
                (j for j in range(i + 1, len(lines)) if close_re.match(lines[j].strip())),
                None,
            )
            if closing is None:
                issues.append(
                    MathSyntaxIssue(i + 1, f"Unterminated display-math delimiter {stripped!r}.")
                )
                i += 1
            else:
                i = closing + 1
            continue
        if stripped.startswith("$$") and not re.match(r"^\$\$.+?\$\$\s*(?:\{[^{}]+\})?$", stripped):
            issues.append(
                MathSyntaxIssue(i + 1, "Unterminated same-line display-math delimiter '$$'.")
            )
        start = 0
        while True:
            opened = line.find(r"\(", start)
            if opened < 0:
                break
            if not _is_escaped(line, opened):
                closed = _find_unescaped(line, r"\)", opened + 2)
                if closed < 0:
                    issues.append(
                        MathSyntaxIssue(i + 1, "Unterminated inline-math delimiter '\\('.")
                    )
                    break
                start = closed + 2
            else:
                start = opened + 2
        i += 1
    if fence is not None and fence[2] and not any(item.line == fence[3] for item in issues):
        issues.append(MathSyntaxIssue(fence[3], "Unterminated math-labelled fenced block."))
    return issues


def _enc(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def decode_inline_math(value: str) -> str:
    pad = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + pad).decode("utf-8")


def normalize_math_syntax(markdown: str) -> str:
    """Shield supported AI/MathJax math before CommonMark parsing.

    Chat applications commonly mix ``$$``/``$`` with ``\\[``/``\\(``, and
    sometimes put TeX in a ``math`` or ``latex`` fence.  This scanner is
    deliberately fence-aware: examples inside ordinary code blocks must remain
    code, while math-labelled fences become native equation blocks.

    The transformation preserves the number of source lines for block math so
    markdown-it source maps remain useful.
    """
    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = markdown.split("\n")
    out: list[str] = []
    i = 0
    fence_char: str | None = None
    fence_size = 0
    math_fence = False
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        fence = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if fence_char is not None:
            is_close = bool(
                fence
                and fence.group(1)[0] == fence_char
                and len(fence.group(1)) >= fence_size
                and not fence.group(2).strip()
            )
            out.append("```" if is_close and math_fence else line)
            if is_close:
                fence_char = None
                fence_size = 0
                math_fence = False
            i += 1
            continue
        if fence:
            marker, raw_info = fence.groups()
            info = raw_info.strip().split(None, 1)[0].lower() if raw_info.strip() else ""
            if info in {"math", "latex", "tex", "mddocx-math"}:
                out.append(f"{line[: len(line) - len(line.lstrip())]}```mddocx-math")
                fence_char = marker[0]
                fence_size = len(marker)
                math_fence = True
            else:
                out.append(line)
                fence_char = marker[0]
                fence_size = len(marker)
                math_fence = False
            i += 1
            continue

        one = re.match(r"^\$\$(.+?)\$\$\s*(\{[^{}]+\})?$", stripped)
        if one:
            out.extend(["```mddocx-math", one.group(1).strip(), "```"])
            if one.group(2):
                out.append(one.group(2))
            i += 1
            continue
        if stripped in {"$$", r"\["}:
            is_dollar = stripped == "$$"
            close_re = (
                re.compile(r"^\$\$\s*(\{[^{}]+\})?$")
                if is_dollar
                else re.compile(r"^\\\]\s*(\{[^{}]+\})?$")
            )
            closing = next(
                (j for j in range(i + 1, len(lines)) if close_re.match(lines[j].strip())),
                None,
            )
            if closing is None:
                # Preserve malformed input instead of swallowing the rest of the
                # document into an unterminated synthetic equation fence.
                out.append(line)
                i += 1
                continue
            i += 1
            body: list[str] = []
            attrs = None
            while i <= closing:
                close_match = close_re.match(lines[i].strip())
                if close_match:
                    attrs = close_match.group(1)
                    i += 1
                    break
                body.append(lines[i])
                i += 1
            out.extend(["```mddocx-math", "\n".join(body), "```"])
            if attrs:
                out.append(attrs)
            continue
        out.append(_shield_inline_math(line))
        i += 1

    return "\n".join(out)


def _shield_inline_math(line: str) -> str:
    """Protect inline math on one Markdown line while respecting code spans."""
    out: list[str] = []
    i = 0
    code_ticks = 0
    while i < len(line):
        if line[i] == "`":
            end = i
            while end < len(line) and line[end] == "`":
                end += 1
            run = end - i
            if code_ticks == 0:
                code_ticks = run
            elif run == code_ticks:
                code_ticks = 0
            out.append(line[i:end])
            i = end
            continue
        if code_ticks:
            out.append(line[i])
            i += 1
            continue

        if line.startswith(r"\(", i) and not _is_escaped(line, i):
            end = _find_unescaped(line, r"\)", i + 2)
            if end >= 0:
                source = line[i + 2 : end]
                out.append(f"{INLINE_SENTINEL}{_enc(source)}ENDMATH")
                i = end + 2
                continue

        if line[i] == "$" and not _is_escaped(line, i) and not line.startswith("$$", i):
            end = _find_inline_dollar_close(line, i + 1)
            if end >= 0:
                source = line[i + 1 : end]
                if line[i + 1].isdigit() and not re.search(r"[\\^_+=*/(){}<>]", source):
                    out.append("$")
                    i += 1
                    continue
                out.append(f"{INLINE_SENTINEL}{_enc(source)}ENDMATH")
                i = end + 1
                continue

        out.append(line[i])
        i += 1
    return "".join(out)


def _is_escaped(text: str, offset: int) -> bool:
    slashes = 0
    offset -= 1
    while offset >= 0 and text[offset] == "\\":
        slashes += 1
        offset -= 1
    return slashes % 2 == 1


def _find_unescaped(text: str, needle: str, start: int) -> int:
    pos = text.find(needle, start)
    while pos >= 0:
        if not _is_escaped(text, pos):
            return pos
        pos = text.find(needle, pos + len(needle))
    return -1


def _find_inline_dollar_close(text: str, start: int) -> int:
    if start >= len(text) or text[start].isspace():
        return -1
    pos = start
    while True:
        pos = text.find("$", pos)
        if pos < 0:
            return -1
        if _is_escaped(text, pos) or (pos + 1 < len(text) and text[pos + 1] == "$"):
            pos += 1
            continue
        if pos == start or text[pos - 1].isspace():
            pos += 1
            continue
        # A closing delimiter immediately followed by a letter or digit is most
        # often a currency range (``$5 to $10``), not inline mathematics.
        if pos + 1 < len(text) and text[pos + 1].isalnum():
            pos += 1
            continue
        return pos


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
            segments.extend(_split_dollars(text[pos : m.start()]))
        segments.append(("math", decode_inline_math(m.group(1))))
        pos = m.end()
    if pos < len(text):
        segments.extend(_split_dollars(text[pos:]))
    return [(kind, value) for kind, value in segments if value]


def _split_dollars(text: str) -> list[tuple[str, str]]:
    # Reuse the same delimiter rules used before Markdown parsing.  Inline
    # content is also parsed independently for footnotes and extensions, and a
    # second permissive dollar parser here used to turn currency ranges into
    # enormous false-positive equations.
    shielded = _shield_inline_math(text)
    sentinel_re = re.compile(rf"{INLINE_SENTINEL}([A-Za-z0-9_-]+)ENDMATH")
    result: list[tuple[str, str]] = []
    pos = 0
    for match in sentinel_re.finditer(shielded):
        if match.start() > pos:
            result.append(("text", shielded[pos : match.start()].replace(r"\$", "$")))
        result.append(("math", decode_inline_math(match.group(1))))
        pos = match.end()
    if pos < len(shielded):
        result.append(("text", shielded[pos:].replace(r"\$", "$")))
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
                    header = _merge_simple_table_lines(lines[i + 1 : header_sep], starts)
                    rows = [
                        _simple_table_cells(line, starts)
                        for line in lines[header_sep + 1 : closing]
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
                    if (candidate and len(candidate) == len(spans)) or re.fullmatch(
                        r"\s*-{10,}\s*", lines[j] or ""
                    ):
                        closing = j
                        break
                    if lines[j].lstrip().startswith("#"):
                        break
                if closing is not None:
                    header = _merge_simple_table_lines(lines[i + 1 : header_sep], starts)
                    rows = [
                        _simple_table_cells(line, starts)
                        for line in lines[header_sep + 1 : closing]
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
            result.append(("text", text[pos : match.start()]))
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
            out.append(lines[i])
            i += 1
            continue
        kind = m.group(1).lower()
        title = (m.group(2) or "").strip()
        body: list[str] = []
        i += 1
        while i < len(lines) and not re.match(r"^\s*:::\s*$", lines[i]):
            body.append(lines[i])
            i += 1
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
            result.append(("text", text[pos : match.start()]))
        result.append(("comment", match.group(1).strip()))
        pos = match.end()
    if pos < len(text):
        result.append(("text", text[pos:]))
    return result or [("text", text)]
