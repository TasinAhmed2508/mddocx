from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re

from .config import MetadataConfig

# Keys that are meaningful mddocx rendering configuration. These are preserved even
# when an AI-export metadata block is stripped. Document identity/provenance fields
# (title/author/created_at/etc.) are intentionally excluded from this set because an
# AI export can populate them and accidentally leak that provenance into DOCX core
# properties.
_MDDOCX_RENDER_KEYS = {
    "theme",
    "page_size",
    "orientation",
    "rtl",
    "toc",
    "page_numbers",
    "auto_landscape_tables",
    "header",
    "footer",
    "notes",
    "bibliography",
    "citation_style",
    "auto_bibliography",
    "title_page",
    "subtitle",
    "organization",
    "title_date",
    "abstract",
    "abstract_title",
    "heading_numbering",
    "heading_numbering_depth",
    "equation_numbering",
    "caption_numbering",
    "code_line_numbers",
    "syntax_highlighting",
    "page_x_of_y",
}

_DOCUMENT_IDENTITY_KEYS = {
    "title",
    "author",
    "subject",
    "keywords",
    "comments",
    "created_at",
    "modified_at",
    "updated_at",
    "date",
    "created",
    "modified",
}

# High-confidence provenance keys used by many conversation export tools. The
# sanitizer is deliberately provider-agnostic: behavior is driven by semantic
# metadata keys rather than one vendor's exact export layout.
_STRONG_EXPORT_KEYS = {
    "conversation_id",
    "conversationid",
    "chat_id",
    "chatid",
    "thread_id",
    "threadid",
    "message_id",
    "messageid",
    "export_id",
    "exportid",
    "model_slug",
    "model_name",
    "system_fingerprint",
    "assistant_id",
    "gizmo_id",
    "current_node",
    "conversation_url",
    "share_url",
    "source_url",
    "exported_at",
    "exported_on",
    "export_date",
    "export_time",
    "provider",
    "platform",
    "conversation_metadata",
    "chat_metadata",
    "export_metadata",
    "message_count",
    "token_count",
}

_WEAK_EXPORT_KEYS = {
    "model",
    "source",
    "url",
    "id",
    "created_at",
    "updated_at",
    "modified_at",
    "generated_at",
    "generated_on",
    "exported",
    "created",
    "updated",
    "last_updated",
    "timestamp",
    "date",
    "time",
    "account",
    "user_id",
    "workspace",
    "branch",
    "locale",
    "language",
}

_BODY_METADATA_KEYS = (
    _STRONG_EXPORT_KEYS
    | _WEAK_EXPORT_KEYS
    | {
        "conversation",
        "chat",
        "engine",
        "temperature",
        "top_p",
        "seed",
        "finish_reason",
        "request_id",
        "response_id",
        "session_id",
        "session",
    }
)

_EXPORT_PHRASE_RE = re.compile(
    r"\b(?:exported|downloaded|saved)\s+(?:from|by)\b|"
    r"\b(?:conversation|chat)\s+export\b|"
    r"\bexport(?:ed)?\s+(?:on|at)\b|"
    r"\b(?:generated|created)\s+by\s+(?:an?\s+)?ai\b",
    re.IGNORECASE,
)
_METADATA_HEADING_RE = re.compile(
    r"^[ \t]{0,3}#{1,6}[ \t]+(?:conversation[ \t]+|chat[ \t]+|ai[ \t]+|"
    r"export[ \t]+|session[ \t]+)?(?:metadata|details|information)[ \t]*#*[ \t]*$",
    re.IGNORECASE,
)
_KEY_VALUE_RE = re.compile(
    r"^[ \t]*(?:(?:[-*+]|>)\s+)?(?:\*\*)?"
    r"(?P<key>[A-Za-z][A-Za-z0-9 _./-]{0,48})(?:\*\*)?[ \t]*[:=][ \t]*(?P<value>.*)$"
)
_YAML_KEY_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_.-]*)[ \t]*:")
_ROLE_RE = re.compile(
    r"^[ \t]{0,3}(?:#{1,6}[ \t]+)?(?:\*\*)?(?:user|you|human|assistant|ai|system)"
    r"(?:\*\*)?[ \t]*:?[ \t]*$",
    re.IGNORECASE,
)
_TIMESTAMP_RE = re.compile(
    r"^[ \t]*(?:\[|\()?"
    r"(?:\d{4}-\d{2}-\d{2}(?:[T ][0-2]\d:[0-5]\d(?::[0-5]\d(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?"
    r"|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s+\d{4}"
    r"(?:\s+(?:at\s+)?\d{1,2}:\d{2}(?:\s*[AP]M)?)?)"
    r"(?:\]|\))?[ \t]*$",
    re.IGNORECASE,
)
_FENCE_OPEN_RE = re.compile(
    r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[ \t]*(?P<lang>json|ya?ml|toml)?[ \t]*$", re.IGNORECASE
)


def _norm_key(value: str) -> str:
    value = value.strip().lower().replace("-", "_").replace(".", "_").replace("/", "_")
    return re.sub(r"\s+", "_", value)


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    if line.endswith("\r"):
        return "\r"
    return ""


def _blank(line: str) -> str:
    return _line_ending(line)


@dataclass(frozen=True, slots=True)
class MetadataSanitizationReport:
    policy: str
    detected_export_metadata: bool = False
    removed_lines: int = 0
    removed_blocks: int = 0
    removed_front_matter_keys: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.removed_lines or self.removed_front_matter_keys)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass(slots=True)
class _MutableReport:
    policy: str
    detected: bool = False
    removed_lines: set[int] = field(default_factory=set)
    removed_blocks: int = 0
    removed_front_keys: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def freeze(self) -> MetadataSanitizationReport:
        return MetadataSanitizationReport(
            policy=self.policy,
            detected_export_metadata=self.detected,
            removed_lines=len(self.removed_lines),
            removed_blocks=self.removed_blocks,
            removed_front_matter_keys=tuple(dict.fromkeys(self.removed_front_keys)),
            reasons=tuple(dict.fromkeys(self.reasons)),
        )


@dataclass(frozen=True, slots=True)
class SanitizedMarkdown:
    markdown: str
    report: MetadataSanitizationReport


def sanitize_markdown_metadata(
    markdown: str, config: MetadataConfig | None = None
) -> SanitizedMarkdown:
    """Remove high-confidence AI/chat export metadata while preserving document content.

    The default ``auto`` policy is conservative: it only removes boundary metadata
    when export provenance is strongly indicated. ``strip`` applies the same semantic
    rules more aggressively. ``keep`` leaves the source untouched.

    Removed source lines are replaced with blank lines so parser diagnostics keep the
    original source line numbers.
    """
    cfg = config or MetadataConfig()
    policy = cfg.ai_export
    if policy == "keep" or not markdown:
        report = MetadataSanitizationReport(policy=policy)
        if policy == "keep" and _looks_like_export(markdown):
            report = MetadataSanitizationReport(
                policy=policy,
                detected_export_metadata=True,
                reasons=("AI/chat export metadata detected but preservation was requested.",),
            )
        return SanitizedMarkdown(markdown, report)

    lines = markdown.splitlines(keepends=True)
    report = _MutableReport(policy=policy)

    body_start, body_end, front_keys = _front_matter_layout(lines)
    export_front = _front_matter_looks_exported(front_keys)
    if export_front:
        report.detected = True
        report.reasons.append("export/provenance fields detected in YAML front matter")
    if body_start > 0 and (export_front or policy == "strip") and cfg.strip_front_matter_provenance:
        _strip_front_matter_keys(lines, front_keys, export_front, policy, report)

    fenced = _code_fence_mask(lines, body_start, body_end)
    if cfg.strip_html_metadata_comments:
        _strip_metadata_comments(lines, body_start, body_end, policy, report, fenced)
    if cfg.strip_boundary_metadata:
        _strip_metadata_sections(lines, body_start, body_end, policy, report, fenced)
        _strip_boundary_fences(lines, body_start, body_end, policy, report)
        _strip_boundary_runs(lines, body_start, body_end, policy, report, fenced)
    if cfg.strip_role_timestamps and (policy == "strip" or report.detected):
        _strip_role_timestamps(lines, body_start, body_end, report, fenced)

    return SanitizedMarkdown("".join(lines), report.freeze())


def _looks_like_export(markdown: str) -> bool:
    lines = markdown.splitlines()
    _, _, front = _front_matter_layout([line + "\n" for line in lines])
    if _front_matter_looks_exported(front):
        return True
    boundary = lines[:80] + lines[-80:]
    return any(
        _EXPORT_PHRASE_RE.search(line) or _metadata_key(line) in _STRONG_EXPORT_KEYS
        for line in boundary
    )


def _front_matter_layout(lines: list[str]) -> tuple[int, int, list[tuple[str, int, int]]]:
    if not lines or lines[0].strip() != "---":
        return 0, len(lines), []
    close = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() in {"---", "..."}:
            close = idx
            break
    if close is None:
        return 0, len(lines), []
    keys: list[tuple[str, int, int]] = []
    starts: list[tuple[str, int]] = []
    for idx in range(1, close):
        if lines[idx].startswith((" ", "\t")):
            continue
        match = _YAML_KEY_RE.match(lines[idx].rstrip("\r\n"))
        if match:
            starts.append((_norm_key(match.group("key")), idx))
    for pos, (key, start) in enumerate(starts):
        end = starts[pos + 1][1] if pos + 1 < len(starts) else close
        keys.append((key, start, end))
    return close + 1, len(lines), keys


def _front_matter_looks_exported(keys: list[tuple[str, int, int]]) -> bool:
    names = {key for key, _, _ in keys}
    if names & _STRONG_EXPORT_KEYS:
        return True
    weak = names & _WEAK_EXPORT_KEYS
    return "model" in weak and len(weak) >= 2


def _strip_front_matter_keys(
    lines: list[str],
    keys: list[tuple[str, int, int]],
    export_front: bool,
    policy: str,
    report: _MutableReport,
) -> None:
    for key, start, end in keys:
        remove = key in _STRONG_EXPORT_KEYS or key in _WEAK_EXPORT_KEYS
        if export_front and key in _DOCUMENT_IDENTITY_KEYS:
            remove = True
        # In force-strip mode identity fields are also treated as metadata, but mddocx
        # render configuration remains intact.
        if policy == "strip" and key in _DOCUMENT_IDENTITY_KEYS:
            remove = True
        if key in _MDDOCX_RENDER_KEYS:
            remove = False
        if not remove:
            continue
        report.detected = report.detected or key in _STRONG_EXPORT_KEYS or export_front
        report.removed_front_keys.append(key)
        for idx in range(start, end):
            if lines[idx].strip():
                report.removed_lines.add(idx)
            lines[idx] = _blank(lines[idx])


def _strip_metadata_comments(
    lines: list[str],
    body_start: int,
    body_end: int,
    policy: str,
    report: _MutableReport,
    fenced: set[int],
) -> None:
    i = body_start
    boundary_limit = 120
    while i < body_end:
        if i in fenced or "<!--" not in lines[i]:
            i += 1
            continue
        start = i
        content = [lines[i]]
        while "-->" not in content[-1] and i + 1 < body_end:
            i += 1
            content.append(lines[i])
        text = "".join(content)
        near_boundary = start < body_start + boundary_limit or start >= body_end - boundary_limit
        score, strong = _metadata_score(text.splitlines())
        should_remove = (
            _EXPORT_PHRASE_RE.search(text) is not None
            or strong
            or (policy == "strip" and near_boundary and score >= 1)
        )
        if should_remove and (near_boundary or strong or _EXPORT_PHRASE_RE.search(text)):
            _blank_range(lines, start, i + 1, report)
            report.removed_blocks += 1
            report.detected = True
            report.reasons.append("export metadata HTML comment")
        i += 1


def _strip_metadata_sections(
    lines: list[str],
    body_start: int,
    body_end: int,
    policy: str,
    report: _MutableReport,
    fenced: set[int],
) -> None:
    boundary = 140
    i = body_start
    while i < body_end:
        stripped = lines[i].rstrip("\r\n")
        if i in fenced or not _METADATA_HEADING_RE.match(stripped):
            i += 1
            continue
        if i >= body_start + boundary and i < body_end - boundary:
            i += 1
            continue
        heading_level = len(stripped.lstrip().split(" ", 1)[0])
        j = i + 1
        while j < body_end:
            candidate = lines[j].lstrip()
            if candidate.startswith("#"):
                match = re.match(r"^(#{1,6})\s", candidate)
                if match and len(match.group(1)) <= heading_level:
                    break
            j += 1
        score, strong = _metadata_score([line.rstrip("\r\n") for line in lines[i + 1 : j]])
        if strong or score >= (1 if policy == "strip" else 2):
            _blank_range(lines, i, j, report)
            report.removed_blocks += 1
            report.detected = True
            report.reasons.append("explicit metadata section")
        i = max(j, i + 1)


def _strip_boundary_fences(
    lines: list[str], body_start: int, body_end: int, policy: str, report: _MutableReport
) -> None:
    for region_start, region_end in _boundary_regions(body_start, body_end, 100):
        i = region_start
        while i < region_end:
            match = _FENCE_OPEN_RE.match(lines[i].rstrip("\r\n"))
            if not match:
                i += 1
                continue
            marker = match.group("fence")
            j = i + 1
            while j < body_end:
                if lines[j].lstrip().startswith(marker[0] * len(marker)):
                    break
                j += 1
            if j >= body_end:
                break
            inner_lines = [line.rstrip("\r\n") for line in lines[i + 1 : j]]
            score, strong = _metadata_score(inner_lines)
            explicit_export = any(_EXPORT_PHRASE_RE.search(line) for line in inner_lines)
            if (policy == "strip" and (strong or score >= 2)) or (
                policy == "auto" and explicit_export
            ):
                _blank_range(lines, i, j + 1, report)
                report.removed_blocks += 1
                report.detected = True
                report.reasons.append("structured export metadata block")
            i = j + 1


def _strip_boundary_runs(
    lines: list[str],
    body_start: int,
    body_end: int,
    policy: str,
    report: _MutableReport,
    fenced: set[int],
) -> None:
    for region_start, region_end in _boundary_regions(body_start, body_end, 100):
        i = region_start
        while i < region_end:
            if i in fenced:
                i += 1
                continue
            if not lines[i].strip():
                i += 1
                continue
            start = i
            recognized = 0
            recognized_keys: set[str] = set()
            strong = False
            export_phrase = False
            nonblank = 0
            j = i
            while j < region_end:
                if j in fenced:
                    break
                text = lines[j].rstrip("\r\n")
                if not text.strip():
                    # Keep short blank gaps inside metadata runs.
                    if j + 1 < region_end and _is_metadata_line(lines[j + 1]):
                        j += 1
                        continue
                    break
                nonblank += 1
                key = _metadata_key(text)
                if key in _BODY_METADATA_KEYS:
                    recognized += 1
                    recognized_keys.add(key)
                    strong = strong or key in _STRONG_EXPORT_KEYS
                if _EXPORT_PHRASE_RE.search(text):
                    export_phrase = True
                if not _is_metadata_line(text) and not _EXPORT_PHRASE_RE.search(text):
                    break
                j += 1
            temporal_or_export = bool(
                recognized_keys
                & {
                    "created_at",
                    "updated_at",
                    "modified_at",
                    "generated_at",
                    "generated_on",
                    "created",
                    "updated",
                    "last_updated",
                    "exported",
                    "timestamp",
                    "date",
                    "time",
                    "exported_at",
                    "export_date",
                    "export_time",
                }
            )
            auto_signature = "model" in recognized_keys and temporal_or_export and recognized >= 2
            should_remove = (
                export_phrase
                or strong
                or (policy == "strip" and recognized >= 1)
                or (policy == "auto" and auto_signature)
            )
            if should_remove:
                _blank_range(lines, start, max(j, start + 1), report)
                report.removed_blocks += 1
                report.detected = True
                report.reasons.append("boundary export metadata")
                i = max(j, start + 1)
            else:
                i = start + 1


def _strip_role_timestamps(
    lines: list[str], body_start: int, body_end: int, report: _MutableReport, fenced: set[int]
) -> None:
    for idx in range(body_start, body_end - 1):
        if idx in fenced or not _ROLE_RE.match(lines[idx].rstrip("\r\n")):
            continue
        j = idx + 1
        while j < min(body_end, idx + 3) and not lines[j].strip():
            j += 1
        if j < body_end and _TIMESTAMP_RE.match(lines[j].rstrip("\r\n")):
            if lines[j].strip():
                report.removed_lines.add(j)
            lines[j] = _blank(lines[j])
            report.removed_blocks += 1
            report.detected = True
            report.reasons.append("standalone timestamp attached to a conversation role")


def _code_fence_mask(lines: list[str], start: int, end: int) -> set[int]:
    protected: set[int] = set()
    active_char: str | None = None
    active_len = 0
    for idx in range(start, end):
        stripped = lines[idx].lstrip()
        match = re.match(r"^(`{3,}|~{3,})", stripped)
        if active_char is None:
            if match:
                marker = match.group(1)
                active_char = marker[0]
                active_len = len(marker)
                protected.add(idx)
            continue
        protected.add(idx)
        if match and match.group(1)[0] == active_char and len(match.group(1)) >= active_len:
            active_char = None
            active_len = 0
    return protected


def _boundary_regions(start: int, end: int, window: int) -> list[tuple[int, int]]:
    if end - start <= window * 2:
        return [(start, end)]
    return [(start, min(end, start + window)), (max(start, end - window), end)]


def _metadata_key(line: str) -> str | None:
    match = _KEY_VALUE_RE.match(line)
    if not match:
        return None
    return _norm_key(match.group("key"))


def _is_metadata_line(line: str) -> bool:
    key = _metadata_key(line.rstrip("\r\n"))
    return key in _BODY_METADATA_KEYS if key else False


def _metadata_score(lines: list[str]) -> tuple[int, bool]:
    score = 0
    strong = False
    for line in lines:
        key = _metadata_key(line)
        if key in _BODY_METADATA_KEYS:
            score += 1
            strong = strong or key in _STRONG_EXPORT_KEYS
        elif _EXPORT_PHRASE_RE.search(line):
            score += 2
            strong = True
        else:
            normalized = (
                _norm_key(line.strip(" \t\"'{}[],").split(":", 1)[0]) if ":" in line else ""
            )
            if normalized in _BODY_METADATA_KEYS:
                score += 1
                strong = strong or normalized in _STRONG_EXPORT_KEYS
    return score, strong


def _blank_range(lines: list[str], start: int, end: int, report: _MutableReport) -> None:
    for idx in range(start, min(end, len(lines))):
        if lines[idx].strip():
            report.removed_lines.add(idx)
        lines[idx] = _blank(lines[idx])


def scrub_generated_docx_core_properties(
    blob: bytes, config: MetadataConfig, *, template_used: bool, explicit: dict[str, bool]
) -> bytes:
    """Remove python-docx's synthetic core-property defaults from generated DOCX files.

    Explicit user document properties are preserved. Template metadata is preserved by
    default because it may be intentional corporate/document-template information.
    """
    if not config.scrub_generated_docx_properties or template_used:
        return blob
    import io
    import zipfile
    from lxml import etree

    source = io.BytesIO(blob)
    output = io.BytesIO()
    namespaces = {
        "dc": "http://purl.org/dc/elements/1.1/",
        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
        "dcterms": "http://purl.org/dc/terms/",
    }
    remove_if_not_explicit = {
        "title": ("dc", "title"),
        "author": ("dc", "creator"),
        "subject": ("dc", "subject"),
        "keywords": ("cp", "keywords"),
        "comments": ("dc", "description"),
        "created_at": ("dcterms", "created"),
        "modified_at": ("dcterms", "modified"),
    }
    with (
        zipfile.ZipFile(source, "r") as zin,
        zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zout,
    ):
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "docProps/core.xml":
                root = etree.fromstring(data)
                for field, (prefix, local) in remove_if_not_explicit.items():
                    if explicit.get(field, False):
                        continue
                    qname = f"{{{namespaces[prefix]}}}{local}"
                    for node in list(root.findall(qname)):
                        root.remove(node)
                if not explicit.get("author", False):
                    qname = f"{{{namespaces['cp']}}}lastModifiedBy"
                    for node in list(root.findall(qname)):
                        root.remove(node)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            zout.writestr(item, data)
    return output.getvalue()
