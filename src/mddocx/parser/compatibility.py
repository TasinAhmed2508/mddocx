from __future__ import annotations

import base64
import binascii
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
                # Currency/range guard: never pair across a code span or across
                # another "$" that _find skipped (e.g. "$5 to $10. ... `$x$`").
                # Such a span is a false-positive range, not math.  Treating
                # the opener as literal lets the later "$"s resolve (or stay
                # literal) on their own.  A former digit-only guard ("$0$" ->
                # literal) left its closer dangling, which then paired with the
                # *next* opener and corrupted the line into invalid base64
                # (UnicodeDecodeError 0xc0), so "$<digits>$" stays math.
                if "`" in source or "$" in source:
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
        decoded = _try_decode_inline_math(m.group(1))
        if decoded is None:
            # Not a payload we produced (literal text or corrupted stream):
            # keep it as text instead of crashing the conversion.
            segments.append(("text", m.group(0)))
        else:
            segments.append(("math", decoded))
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
        decoded = _try_decode_inline_math(match.group(1))
        if decoded is None:
            result.append(("text", match.group(0)))
        else:
            result.append(("math", decoded))
        pos = match.end()
    if pos < len(shielded):
        result.append(("text", shielded[pos:].replace(r"\$", "$")))
    return result


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
