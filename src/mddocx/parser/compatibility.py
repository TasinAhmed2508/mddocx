from __future__ import annotations

import base64
import binascii
from collections.abc import Iterator
from dataclasses import dataclass
import re

from markdown_it.common.html_re import HTML_TAG_RE
from markdown_it.helpers import parseLinkDestination, parseLinkTitle
from markdown_it.rules_block import StateBlock

from .tables import html_table_source_end

INLINE_SENTINEL = "MDDOCXMATH"
# The colon frames adjacent payloads, while Z keeps a final underscore inside a word.
_INLINE_MATH_END = "Z:ENDMATH"
_INLINE_MATH_SENTINEL = re.compile(rf"{INLINE_SENTINEL}([A-Za-z0-9_-]+){_INLINE_MATH_END}")
_LINK_MARK = re.compile(r"\]\(|\]:|<|https?://", re.I)
_MATH_MARK = re.compile(r"[`\\$]|" + _LINK_MARK.pattern, re.I)
_REFERENCE_LABEL = re.compile(r"^\s*\[(?!\^)(?:[^\[\]\\]|\\.)+\]$")
_RAW_URL = re.compile(r"https?://[^<>\s]+", re.I)
_DISPLAY_CLOSE = {
    "$$": re.compile(r"^\$\$\s*(\{[^{}]+\})?$"),
    r"\[": re.compile(r"^\\\]\s*(\{[^{}]+\})?$"),
    r"\\[": re.compile(r"^\\\\\]\s*(\{[^{}]+\})?$"),
}
_SAME_LINE_SLASH_DISPLAY = re.compile(r"^(\\{1,2})\[(.+?)(?<!\\)\1\]\s*(\{[^{}]+\})?$")
_EXPORTED_TEX_ESCAPES = re.compile(r"(?<!\\)(?:\\(?=_)|\\(?=\\%)|\\(?=\\\\[ \t]))")


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

        if (table_end := html_table_source_end(lines, i)) > i:
            i = table_end
            continue
        stripped = line.strip()
        if close_re := _DISPLAY_CLOSE.get(stripped):
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
        for _ in _inline_math_parts(line, start_line=i + 1, issues=issues):
            pass
        i += 1
    if fence is not None and fence[2] and not any(item.line == fence[3] for item in issues):
        issues.append(MathSyntaxIssue(fence[3], "Unterminated math-labelled fenced block."))
    return issues


def _enc(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def decode_inline_math(value: str) -> str:
    """Decode a shielded inline-math payload.

    Payloads are always produced by :func:`_enc` (UTF-8 -> URL-safe base64),
    so a decode failure means the sentinel regex matched unrelated literal
    text (or a corrupted stream) and the caller must treat it as plain text
    instead of crashing the whole conversion with ``UnicodeDecodeError``.
    """
    pad = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + pad).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid inline-math payload {value!r}: {exc}") from exc


def _try_decode_inline_math(value: str) -> str | None:
    """Return the decoded payload, or ``None`` when it is not valid math."""
    try:
        return decode_inline_math(value)
    except ValueError:
        return None


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

        if (table_end := html_table_source_end(lines, i)) > i:
            out.extend(lines[i:table_end])
            i = table_end
            continue

        one = re.match(r"^\$\$(.+?)\$\$\s*(\{[^{}]+\})?$", stripped)
        if one:
            out.extend(["```mddocx-math", one.group(1).strip(), "```"])
            if one.group(2):
                out.append(one.group(2))
            i += 1
            continue
        if _SAME_LINE_SLASH_DISPLAY.fullmatch(stripped):
            out.append(line)
            i += 1
            continue
        if close_re := _DISPLAY_CLOSE.get(stripped):
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
            body = "\n".join(lines[i + 1 : closing])
            if stripped == r"\\[":
                body = _unescape_exported_tex(body)
            close_match = close_re.match(lines[closing].strip())
            assert close_match is not None
            attrs = close_match.group(1)
            out.extend(["```mddocx-math", body, "```"])
            if attrs:
                out.append(attrs)
            i = closing + 1
            continue
        out.append(shield_inline_math(line))
        i += 1

    return "\n".join(out)


def slash_display_block(state: StateBlock, start_line: int, end_line: int, silent: bool) -> bool:
    """Read a standalone same-line equation without shifting subsequent source positions."""
    if state.sCount[start_line] - state.blkIndent >= 4:
        return False
    start = state.bMarks[start_line] + state.tShift[start_line]
    line = state.src[start : state.eMarks[start_line]].rstrip()
    match = _SAME_LINE_SLASH_DISPLAY.fullmatch(line)
    if match is None:
        return False
    if not silent:
        slashes, body, attrs = match.groups()
        token = state.push("mddocx_display_math", "", 0)
        token.map = [start_line, start_line + 1]
        token.content = _unescape_exported_tex(body) if len(slashes) == 2 else body
        token.info = attrs or ""
        state.line = start_line + 1
    return True


def _unescape_exported_tex(body: str) -> str:
    # Chat exports escape subscripts, percent signs, and flattened matrix row separators.
    return _EXPORTED_TEX_ESCAPES.sub("", body)


def shield_inline_math(line: str) -> str:
    """Protect inline math on one Markdown line while respecting code spans."""
    if "$" not in line and "\\" not in line:
        return line
    return "".join(
        f"{INLINE_SENTINEL}{_enc(value)}{_INLINE_MATH_END}" if kind == "math" else value
        for kind, value in _inline_math_parts(line)
    )


def split_cell_math(
    text: str, start_line: int, issues: list[MathSyntaxIssue]
) -> Iterator[tuple[str, str]]:
    """Read TeX delimiters from an HTML text node, leaving its markup untouched."""
    yield from _inline_math_parts(
        text, display_delimiters=True, start_line=start_line, issues=issues
    )


def _link_literal_end(text: str, offset: int, marker: str) -> int:
    if marker == "<":
        tag = HTML_TAG_RE.match(text, offset)
        return tag.end() if tag else offset + 1
    if marker[0].lower() == "h":
        url = _RAW_URL.match(text, offset)
        return url.end() if url else offset + len(marker)
    inline = marker == "](" and text.find("[", 0, offset) >= 0 and not _is_escaped(text, offset)
    reference = marker == "]:" and _REFERENCE_LABEL.fullmatch(text, 0, offset + 1)
    if not (inline or reference):
        return offset + len(marker)
    start = offset + 2
    while start < len(text) and text[start] in " \t":
        start += 1
    destination = parseLinkDestination(text, start, len(text))
    if not destination.ok:
        return start
    end = destination.pos
    title_start = end
    while title_start < len(text) and text[title_start] in " \t":
        title_start += 1
    if title_start > end:
        title = parseLinkTitle(text, title_start, len(text))
        if title.ok:
            end = title.pos
    return end


def _inline_math_parts(
    text: str,
    *,
    display_delimiters: bool = False,
    start_line: int = 1,
    issues: list[MathSyntaxIssue] | None = None,
) -> Iterator[tuple[str, str]]:
    if "$" not in text and "\\" not in text:
        if text:
            yield "text", text
        return
    start = cursor = 0
    code_ticks = 0
    while mark := _MATH_MARK.search(text, cursor):
        i = mark.start()
        cursor = i + 1
        if mark[0] == "`":
            end = cursor
            while end < len(text) and text[end] == "`":
                end += 1
            run = end - i
            if code_ticks == 0:
                code_ticks = run
            elif run == code_ticks:
                code_ticks = 0
            cursor = end
            continue
        if code_ticks:
            continue
        if mark[0] not in {"\\", "$"}:
            if not display_delimiters:
                cursor = _link_literal_end(text, i, mark[0])
            continue

        opener = text[i : i + 2]
        exported = text.startswith(r"\\(", i) or (display_delimiters and text.startswith(r"\\[", i))
        if exported:
            opener = text[i : i + 3]
            closer = r"\\)" if opener == r"\\(" else r"\\]"
        else:
            closer = r"\)" if opener == r"\(" else None
        if display_delimiters and closer is None:
            closer = {r"\[": r"\]", "$$": "$$"}.get(opener)
        if closer and not _is_escaped(text, i):
            size = len(opener)
            end = _find_unescaped(text, closer, i + size)
            if end < 0 and issues is not None and not exported:
                line = start_line + text.count("\n", 0, i)
                scope = "table math" if display_delimiters else "inline-math"
                issues.append(MathSyntaxIssue(line, f"Unterminated {scope} delimiter {opener!r}."))
        elif mark[0] == "$" and opener != "$$" and not _is_escaped(text, i):
            end = _find_inline_dollar_close(text, i + 1)
            # Never pair a currency range across another dollar delimiter or a code span.
            if end >= 0:
                if any(char in text[i + 1 : end] for char in "`$") or (
                    not display_delimiters
                    and any(
                        _link_literal_end(text, link.start(), link[0]) > end
                        for link in _LINK_MARK.finditer(text, i + 1, end)
                    )
                ):
                    end = -1
            size = 1
        else:
            continue
        if end < 0:
            cursor = i + size
            continue
        if start < i:
            yield "text", text[start:i]
        body = text[i + size : end]
        yield "math", _unescape_exported_tex(body) if exported else body
        cursor = start = end + size
    if start < len(text):
        yield "text", text[start:]


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
    """Decode shielded math after Markdown has consumed literal escape characters."""
    segments: list[tuple[str, str]] = []
    pos = 0
    for m in _INLINE_MATH_SENTINEL.finditer(text):
        if m.start() > pos:
            segments.append(("text", text[pos : m.start()]))
        decoded = _try_decode_inline_math(m.group(1))
        if decoded is None:
            # Not a payload we produced (literal text or corrupted stream):
            # keep it as text instead of crashing the conversion.
            segments.append(("text", m.group(0)))
        else:
            segments.append(("math", decoded))
        pos = m.end()
    if pos < len(text):
        segments.append(("text", text[pos:]))
    return [(kind, value) for kind, value in segments if value]


def restore_inline_math_text(text: str) -> str:
    """Recover shielded TeX in metadata, leaving literal dollar signs alone."""
    return _INLINE_MATH_SENTINEL.sub(
        lambda match: _try_decode_inline_math(match[1]) or match[0], text
    )


_FOOTNOTE_DEF_RE = re.compile(r"^ {0,3}\[\^([^\]]+)\]:[ \t]*(.*)$")


def extract_footnote_definitions(markdown: str) -> tuple[str, dict[str, tuple[str, int]]]:
    """Extract common Markdown footnote definitions without touching fenced code.

    Supports the widespread ``[^id]: text`` form plus indented continuation lines.
    Definitions are removed from the body and returned as Markdown fragments so the
    parser can convert them to the same canonical inline AST used elsewhere.
    """
    lines = markdown.split("\n")
    out: list[str] = []
    notes: dict[str, tuple[str, int]] = {}
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

        definition_start = i
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
        notes[label] = ("\n".join(body).strip(), definition_start + 1)
        out.extend([""] * (i - definition_start))
    return "\n".join(out), notes


def split_footnote_references(text: str) -> list[tuple[str, str]]:
    """Split plain inline text into text/reference segments."""
    protected: dict[str, str] = {}
    sentinel_re = re.compile(rf"{FOOTNOTE_ESCAPE_SENTINEL}([A-Za-z0-9_-]+)ENDNOTE")

    def keep_literal(match):
        key = f"\x00FNESC{len(protected)}\x00"
        decoded = _try_decode_inline_math(match.group(1))
        protected[key] = f"[^{decoded}]" if decoded is not None else match.group(0)
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


def normalize_export_citations(markdown: str, *, strip: bool = True) -> str:
    """Repair citation-suffixed closing fences without changing code examples.

    Gemini document exports append numeric citation markers to closing fences,
    making CommonMark consume the rest of the document as code. Only matching
    closers are repaired; citation-like text inside code remains literal.
    """
    citation = r"\[cite:\s*\d+(?:\s*,\s*\d+)*\]"
    active = None
    out = []
    for line in markdown.splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*?)(\r?\n)?$", line)
        if active:
            if match and match[1][0] == active[0] and len(match[1]) >= active[1]:
                tail = match[2].strip()
                if not tail or re.fullmatch(r"(?:" + citation + r"\s*)+", tail):
                    active = None
                    line = match[1] + (match[3] or "")
                    if tail and not strip:
                        line += tail + (match[3] or "\n")
        elif match:
            active = (match[1][0], len(match[1]))
        elif strip:
            # Protect literal inline code while removing numeric export tokens.
            line = "".join(
                part if i % 2 else re.sub(citation, "", part)
                for i, part in enumerate(re.split(r"(`+[^`]*`+)", line))
            )
        out.append(line)
    return "".join(out)
