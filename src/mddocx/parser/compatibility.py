from __future__ import annotations

import base64
import binascii
from bisect import bisect_left
from collections.abc import Iterator
from dataclasses import dataclass
import re

from markdown_it.common.html_re import HTML_TAG_RE
from markdown_it.helpers import parseLinkDestination, parseLinkTitle
from markdown_it.rules_block import StateBlock, fence
from markdown_it.rules_core import StateCore

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
_SAME_LINE_DOLLAR_DISPLAY = re.compile(r"^\$\$(.+?)\$\$\s*(\{[^{}]+\})?$")
_FENCE_LINE = re.compile(r"^(?:\x60{3,}|~{3,})")
_BACKTICKS = re.compile(r"\x60+")
_EXPORTED_TEX_ESCAPES = re.compile(r"(?<!\\)(?:\\(?=_)|\\(?=\\%)|\\(?=\\\\[ \t]))")


@dataclass(frozen=True, slots=True)
class MathSyntaxIssue:
    line: int
    message: str


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


def is_math_fence(info: str) -> bool:
    words = info.split(None, 1)
    return bool(words and words[0].lower() in {"math", "latex", "tex", "mddocx-math"})


def math_aware_fence(state: StateBlock, start: int, end: int, silent: bool) -> bool:
    if not fence(state, start, end, silent):
        return False
    if not silent:
        token = state.tokens[-1]
        if is_math_fence(token.info):
            last = _block_line(state, state.line - 1)
            if (
                state.line == start + 1
                or not last.startswith(token.markup)
                or last.lstrip(token.markup[0]).strip()
            ):
                _block_math_issue(state, start, "Unterminated math-labelled fenced block.")
    return True


def _block_line(state: StateBlock, index: int) -> str:
    start = state.bMarks[index] + state.tShift[index]
    return state.src[start : state.eMarks[index]].rstrip()


def _block_math_issue(state: StateBlock, index: int, message: str) -> None:
    if (issues := state.env.get("mddocx_math_issues")) is not None:
        issues.append(MathSyntaxIssue(index + 1 + state.env.get("mddocx_line_offset", 0), message))


def display_math_block(state: StateBlock, start: int, end: int, silent: bool) -> bool:
    """Recognize wrapped equations at the current Markdown container's indentation."""
    if state.is_code_block(start):
        return False
    line = _block_line(state, start)
    next_line = start + 1
    if match := _SAME_LINE_SLASH_DISPLAY.fullmatch(line):
        slashes, body, attrs = match.groups()
        if len(slashes) == 2:
            body = _unescape_exported_tex(body)
    elif match := _SAME_LINE_DOLLAR_DISPLAY.fullmatch(line):
        body, attrs = match.groups()
    elif close_re := _DISPLAY_CLOSE.get(line):
        while next_line < end:
            if not state.isEmpty(next_line) and state.sCount[next_line] < state.blkIndent:
                break
            current = _block_line(state, next_line)
            if match := close_re.fullmatch(current):
                break
            if current in _DISPLAY_CLOSE or _FENCE_LINE.match(current):
                break
            next_line += 1
        if match is None:
            if not silent:
                _block_math_issue(state, start, f"Unterminated display-math delimiter {line!r}.")
            return False
        body = state.getLines(start + 1, next_line, state.blkIndent, False)
        if line == r"\\[":
            body = _unescape_exported_tex(body)
        attrs = match.group(1)
        next_line += 1
    else:
        if not silent and line.startswith("$$"):
            _block_math_issue(state, start, "Unterminated same-line display-math delimiter '$$'.")
        return False
    if not silent:
        token = state.push("mddocx_display_math", "", 0)
        token.map = [start, next_line]
        token.content = body
        token.info = attrs or ""
        state.line = next_line
    return True


def shield_inline_tokens(state: StateCore) -> None:
    if state.inlineMode:
        return
    for token in state.tokens:
        if token.type == "inline":
            start = token.map[0] + 1 if token.map else 1
            token.content = shield_inline_math(
                token.content,
                start_line=start + state.env.get("mddocx_line_offset", 0),
                issues=state.env.get("mddocx_math_issues"),
            )


def _unescape_exported_tex(body: str) -> str:
    # Chat exports escape subscripts, percent signs, and flattened matrix row separators.
    return _EXPORTED_TEX_ESCAPES.sub("", body)


def shield_inline_math(
    text: str, *, start_line: int = 1, issues: list[MathSyntaxIssue] | None = None
) -> str:
    """Protect math in Markdown inline content, including around wrapped code spans."""
    if "$" not in text and "\\" not in text:
        return text
    return "".join(
        f"{INLINE_SENTINEL}{_enc(value)}{_INLINE_MATH_END}" if kind == "math" else value
        for kind, value in _inline_math_parts(text, start_line=start_line, issues=issues)
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
    tick_positions: dict[int, list[int]] | None = None
    line_end = text.find("\n") if not display_delimiters else -1
    while mark := _MATH_MARK.search(text, cursor):
        i = mark.start()
        cursor = i + 1
        if 0 <= line_end < i:
            line_end = text.find("\n", i)
        limit = len(text) if line_end < 0 else line_end
        if mark[0] == "`":
            if _is_escaped(text, i):
                continue
            end = cursor
            while end < len(text) and text[end] == "`":
                end += 1
            run = end - i
            if tick_positions is None:
                tick_positions = {}
                for ticks in _BACKTICKS.finditer(text):
                    tick_positions.setdefault(len(ticks[0]), []).append(ticks.start())
            candidates = tick_positions.get(run, [])
            closing = bisect_left(candidates, end)
            if closing < len(candidates):
                end = candidates[closing] + run
            cursor = end
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
            end = _find_unescaped(text, closer, i + size, limit)
            if end < 0 and issues is not None and not exported:
                line = start_line + text.count("\n", 0, i)
                scope = "table math" if display_delimiters else "inline-math"
                issues.append(MathSyntaxIssue(line, f"Unterminated {scope} delimiter {opener!r}."))
        elif mark[0] == "$" and opener != "$$" and not _is_escaped(text, i):
            end = _find_inline_dollar_close(text, i + 1, limit)
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


def _find_unescaped(text: str, needle: str, start: int, limit: int) -> int:
    pos = text.find(needle, start, limit)
    while pos >= 0:
        if not _is_escaped(text, pos):
            return pos
        pos = text.find(needle, pos + len(needle), limit)
    return -1


def _find_inline_dollar_close(text: str, start: int, limit: int) -> int:
    if start >= limit or text[start].isspace():
        return -1
    pos = start
    while True:
        pos = text.find("$", pos, limit)
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
                    if tail:
                        indent = line[: match.start(1)]
                        if strip:
                            line = indent + match[1] + (match[3] or "")
                        else:
                            newline = match[3] or "\n"
                            line = indent + match[1] + newline + indent + tail + newline
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
