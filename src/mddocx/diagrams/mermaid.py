from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

_FLOW_NODE_WIDTH = 240
_FLOW_NODE_HEIGHT = 120
_FLOW_HORIZONTAL_GAP = 300
_FLOW_VERTICAL_GAP = 210
_FLOW_ITEM_GAP = 285
_FLOW_MARGIN = 70


class MermaidRenderError(ValueError):
    pass


@dataclass(slots=True)
class _Node:
    ident: str
    label: str
    shape: str = "rect"


@dataclass(slots=True)
class _Edge:
    src: str
    dst: str
    label: str = ""


class MermaidRenderer:
    """Small, deterministic, offline renderer for common Mermaid diagrams.

    It intentionally supports a bounded subset (flowchart/graph/sequenceDiagram)
    rather than pretending to be a full Mermaid JavaScript implementation. Unknown
    diagram families fail cleanly so callers can preserve the source as editable code.
    """

    def __init__(
        self, *, max_source_chars: int = 100_000, max_nodes: int = 500, max_edges: int = 1_000
    ):
        self.max_source_chars = max_source_chars
        self.max_nodes = max_nodes
        self.max_edges = max_edges

    def render(self, source: str, output_dir: Path) -> Path:
        if len(source) > self.max_source_chars:
            raise MermaidRenderError("Mermaid source exceeds configured size limit.")
        lines = [
            line.rstrip() for line in source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        ]
        significant_raw = [
            line for line in lines if line.strip() and not line.lstrip().startswith("%%")
        ]
        significant = [line.strip() for line in significant_raw]
        if not significant:
            raise MermaidRenderError("Empty Mermaid diagram.")
        first = significant[0]
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        target = output_dir / f"mermaid-{digest}.png"
        if target.exists():
            return target
        if re.match(r"^(?:flowchart|graph)\b", first, flags=re.I):
            self._render_flowchart(significant, target)
        elif first.lower() == "sequencediagram":
            self._render_sequence(significant, target)
        elif re.match(r"^pie\b", first, flags=re.I):
            self._render_pie(significant, target)
        elif re.match(r"^erDiagram\b", first, flags=re.I):
            self._render_er(significant, target)
        elif re.match(r"^mindmap\b", first, flags=re.I):
            self._render_mindmap(significant_raw, target)
        elif re.match(
            r"^(?:stateDiagram(?:-v2)?|classDiagram|timeline|journey|gantt)\b", first, flags=re.I
        ):
            self._render_structured_text(significant, target)
        else:
            kind = first.split(None, 1)[0]
            raise MermaidRenderError(f"Unsupported Mermaid diagram type: {kind}")
        return target

    def render_pages(
        self, source: str, output_dir: Path, *, width_inches: float, height_inches: float
    ) -> tuple[list[Path], list[str], list[str]]:
        """Split long flowcharts at overlapping levels so text remains legible in Word."""
        if len(source) > self.max_source_chars:
            raise MermaidRenderError("Mermaid source exceeds configured size limit.")
        lines = [
            line.strip()
            for line in source.replace("\r", "").split("\n")
            if line.strip() and not line.lstrip().startswith("%%")
        ]
        if not lines or not re.match(r"^(?:flowchart|graph)\b", lines[0], flags=re.I):
            return [self.render(source, output_dir)], [], []
        direction, nodes, edges = self._parse_flow(lines)
        levels = self._levels(nodes, edges)
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        target = output_dir / f"mermaid-{digest}-numbered.png"
        display_labels = {
            node.ident: f"Node {index}"
            for index, node in enumerate((n for n in nodes.values() if not n.label.isascii()), 1)
        }
        node_key = [f"{label}: {nodes[ident].label}" for ident, label in display_labels.items()]
        legend = [
            f"{nodes[edge.src].label} → {nodes[edge.dst].label}: {edge.label}"
            for edge in edges
            if edge.label
        ]
        horizontal = direction in {"LR", "RL"}
        width, height = self._flow_size(levels, horizontal)
        max_width = width_inches * 144
        max_height = max(1.0, height_inches - 0.75) * 144
        if horizontal:
            max_levels = max(
                3,
                int((max_width - 2 * _FLOW_MARGIN - _FLOW_NODE_WIDTH) // _FLOW_HORIZONTAL_GAP) + 1,
            )
        else:
            scale = min(1.0, max_width / width)
            max_levels = max(
                3,
                int(
                    (max_height / scale - 2 * _FLOW_MARGIN - _FLOW_NODE_HEIGHT)
                    // _FLOW_VERTICAL_GAP
                )
                + 1,
            )
        if len(levels) <= max_levels:
            self._render_flowchart(
                lines, target, numbered_edges=True, display_labels=display_labels
            )
            return [target], legend, node_key

        pages: list[Path] = []
        ranges: list[tuple[int, int]] = []
        start = 0
        while start < len(levels):
            end = min(len(levels), start + max_levels)
            ranges.append((start, end))
            gap = _FLOW_HORIZONTAL_GAP if horizontal else _FLOW_VERTICAL_GAP
            extent = (_FLOW_NODE_WIDTH if horizontal else _FLOW_NODE_HEIGHT) // 2
            center = _FLOW_MARGIN + extent
            limit = width if horizontal else height
            first = 0 if start == 0 else max(0, center + start * gap - extent - 2)
            last = (
                limit if end == len(levels) else min(limit, center + (end - 1) * gap + extent + 2)
            )
            if direction in {"RL", "BT"}:
                first, last = limit - last, limit - first
            box = (first, 0, last, height) if horizontal else (0, first, width, last)
            page = target.with_name(f"{target.stem}-part-{len(pages) + 1}.png")
            self._render_flowchart(
                lines,
                page,
                numbered_edges=True,
                display_labels=display_labels,
                visible_nodes={ident for level in levels[start:end] for ident in level},
                crop=box,
            )
            pages.append(page)
            if end == len(levels):
                break
            start = end - 2
        by_level = {ident: index for index, group in enumerate(levels) for ident in group}
        for edge in edges:
            if not edge.label and not any(
                start <= by_level[edge.src] < end and start <= by_level[edge.dst] < end
                for start, end in ranges
            ):
                legend.append(
                    f"Unlabeled connection: {nodes[edge.src].label} → {nodes[edge.dst].label}"
                )
        return pages, legend, node_key

    @staticmethod
    def _font(size: int, bold: bool = False):
        try:
            from PIL import ImageFont
        except ImportError as exc:
            raise MermaidRenderError("Mermaid rendering requires Pillow.") from exc
        candidates = [
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
            "Arial Bold.ttf" if bold else "Arial.ttf",
        ]
        for name in candidates:
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _node_from_token(token: str) -> _Node:
        token = token.strip().rstrip(";")
        match = re.match(r"^([A-Za-z_][\w.-]*)(.*)$", token)
        if not match:
            raise MermaidRenderError(f"Unsupported Mermaid node syntax: {token}")
        ident, suffix = match.group(1), match.group(2).strip()
        if not suffix:
            return _Node(ident, ident)
        patterns = [
            (r"^\(\((.*)\)\)$", "circle"),
            (r"^\(\[(.*)\]\)$", "round"),
            (r"^\{(.*)\}$", "diamond"),
            (r"^\[(.*)\]$", "rect"),
            (r'^\("(.*)"\)$', "round"),
            (r"^\((.*)\)$", "round"),
        ]
        for pattern, shape in patterns:
            m = re.match(pattern, suffix)
            if m:
                return _Node(ident, m.group(1).strip() or ident, shape)
        raise MermaidRenderError(f"Unsupported Mermaid node syntax: {token}")

    @staticmethod
    def _split_flow_chain(line: str) -> tuple[list[str], list[str]]:
        tokens: list[str] = []
        labels: list[str] = []
        stack: list[str] = []
        pairs = {"[": "]", "(": ")", "{": "}"}
        start = i = 0
        quote: str | None = None
        while i < len(line):
            char = line[i]
            if quote:
                if char == quote and (i == 0 or line[i - 1] != "\\"):
                    quote = None
            elif char == '"' and stack:
                quote = char
            elif char in pairs:
                stack.append(pairs[char])
            elif stack and char == stack[-1]:
                stack.pop()
            elif not stack:
                arrow = next(
                    (a for a in ("-->", "---", "-.->", "==>") if line.startswith(a, i)), None
                )
                if arrow:
                    tokens.append(line[start:i].strip())
                    i += len(arrow)
                    while i < len(line) and line[i].isspace():
                        i += 1
                    label = ""
                    if i < len(line) and line[i] == "|":
                        close = line.find("|", i + 1)
                        if close < 0:
                            raise MermaidRenderError("Unclosed Mermaid edge label.")
                        label = line[i + 1 : close].strip()
                        i = close + 1
                    labels.append(label)
                    start = i
                    continue
            i += 1
        if labels:
            tokens.append(line[start:].strip())
        return tokens, labels

    def _parse_flow(self, lines: list[str]):
        head = re.match(r"^(?:flowchart|graph)\s+([A-Za-z]+)", lines[0], flags=re.I)
        direction = head.group(1).upper() if head else "TD"
        nodes: dict[str, _Node] = {}
        edges: list[_Edge] = []
        labeled_re = re.compile(r"^(.*?)\s+--\s*(.*?)\s*-->\s*(.*?)$")
        for line in lines[1:]:
            stripped = line.strip().rstrip(";")
            if not stripped or stripped.startswith(
                ("%%", "classDef ", "class ", "style ", "linkStyle ")
            ):
                continue
            lm = labeled_re.match(stripped)
            if lm:
                left, label, right = lm.groups()
                a, b = self._node_from_token(left), self._node_from_token(right)
                nodes[a.ident] = a if a.label != a.ident or a.ident not in nodes else nodes[a.ident]
                nodes[b.ident] = b if b.label != b.ident or b.ident not in nodes else nodes[b.ident]
                edges.append(_Edge(a.ident, b.ident, label.strip()))
                continue
            parts, labels = self._split_flow_chain(stripped)
            if labels:
                current = self._node_from_token(parts[0])
                nodes[current.ident] = (
                    current
                    if current.label != current.ident or current.ident not in nodes
                    else nodes[current.ident]
                )
                for label, part in zip(labels, parts[1:]):
                    nxt = self._node_from_token(part)
                    nodes[nxt.ident] = (
                        nxt
                        if nxt.label != nxt.ident or nxt.ident not in nodes
                        else nodes[nxt.ident]
                    )
                    edges.append(_Edge(current.ident, nxt.ident, label))
                    current = nxt
                continue
            node = self._node_from_token(stripped)
            if node.label != node.ident or node.ident not in nodes:
                nodes[node.ident] = node
        if not nodes:
            raise MermaidRenderError("No supported Mermaid flowchart nodes were found.")
        if len(nodes) > self.max_nodes or len(edges) > self.max_edges:
            raise MermaidRenderError("Mermaid diagram exceeds configured node/edge limits.")
        return direction, nodes, edges

    @staticmethod
    def _levels(nodes: dict[str, _Node], edges: list[_Edge]) -> list[list[str]]:
        incoming = {n: 0 for n in nodes}
        outgoing: dict[str, list[str]] = {n: [] for n in nodes}
        for e in edges:
            if e.src in nodes and e.dst in nodes:
                incoming[e.dst] += 1
                outgoing[e.src].append(e.dst)
        frontier = [n for n, deg in incoming.items() if deg == 0] or [next(iter(nodes))]
        levels: list[list[str]] = []
        seen: set[str] = set()
        while frontier:
            level = [n for n in frontier if n not in seen]
            if not level:
                break
            levels.append(level)
            seen.update(level)
            nxt: list[str] = []
            for n in level:
                for dst in outgoing[n]:
                    incoming[dst] = max(0, incoming[dst] - 1)
                    if incoming[dst] == 0 and dst not in seen:
                        nxt.append(dst)
            frontier = list(dict.fromkeys(nxt))
        remaining = [n for n in nodes if n not in seen]
        if remaining:
            levels.append(remaining)
        return levels

    @staticmethod
    def _flow_size(levels: list[list[str]], horizontal: bool) -> tuple[int, int]:
        max_items = max(len(level) for level in levels)
        if horizontal:
            width = (
                2 * _FLOW_MARGIN + max(1, len(levels) - 1) * _FLOW_HORIZONTAL_GAP + _FLOW_NODE_WIDTH
            )
            height = 2 * _FLOW_MARGIN + max(1, max_items - 1) * 150 + _FLOW_NODE_HEIGHT
        else:
            width = 2 * _FLOW_MARGIN + max(1, max_items - 1) * _FLOW_ITEM_GAP + _FLOW_NODE_WIDTH
            height = (
                2 * _FLOW_MARGIN + max(1, len(levels) - 1) * _FLOW_VERTICAL_GAP + _FLOW_NODE_HEIGHT
            )
        return max(600, width), max(320, height)

    def _render_flowchart(
        self,
        lines: list[str],
        target: Path,
        *,
        numbered_edges: bool = False,
        display_labels: dict[str, str] | None = None,
        visible_nodes: set[str] | None = None,
        crop: tuple[int, int, int, int] | None = None,
    ) -> None:
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise MermaidRenderError("Mermaid rendering requires Pillow.") from exc
        direction, nodes, edges = self._parse_flow(lines)
        levels = self._levels(nodes, edges)
        horizontal = direction in {"LR", "RL"}
        margin = _FLOW_MARGIN
        width, height = self._flow_size(levels, horizontal)
        if width * height > 40_000_000:
            raise MermaidRenderError("Flowchart is too large to render clearly.")
        positions: dict[str, tuple[float, float]] = {}
        for li, level in enumerate(levels):
            for ni, ident in enumerate(level):
                if horizontal:
                    x = margin + _FLOW_NODE_WIDTH / 2 + li * _FLOW_HORIZONTAL_GAP
                    y = height / 2 + (ni - (len(level) - 1) / 2) * 150
                else:
                    x = width / 2 + (ni - (len(level) - 1) / 2) * _FLOW_ITEM_GAP
                    y = margin + _FLOW_NODE_HEIGHT / 2 + li * _FLOW_VERTICAL_GAP
                positions[ident] = (x, y)
        if direction in {"RL", "BT"}:
            if horizontal:
                positions = {n: (width - x, y) for n, (x, y) in positions.items()}
            else:
                positions = {n: (x, height - y) for n, (x, y) in positions.items()}

        if crop is not None:
            left, top, right, bottom = crop
            positions = {n: (x - left, y - top) for n, (x, y) in positions.items()}
            width, height = right - left, bottom - top
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        font = self._font(18)
        label_font = self._font(15)

        label_number = 0
        grouped: dict[tuple[str, str], list[int]] = {}
        for edge in edges:
            numbers = grouped.setdefault((edge.src, edge.dst), [])
            if edge.label:
                label_number += 1
                numbers.append(label_number)
        by_level = {ident: level for level, group in enumerate(levels) for ident in group}
        for (src, dst), numbers in grouped.items():
            if src == dst:
                raise MermaidRenderError("Self-loop flowcharts are not supported by the renderer.")
            if src not in positions or dst not in positions:
                continue
            if visible_nodes is not None and (src not in visible_nodes or dst not in visible_nodes):
                continue
            sx, sy = positions[src]
            dx, dy = positions[dst]
            if abs(by_level[src] - by_level[dst]) > 1:
                mx, my = self._long_arrow(draw, sx, sy, dx, dy, width, height, horizontal)
            else:
                self._arrow(draw, sx, sy, dx, dy)
                mx, my = (sx + dx) / 2, (sy + dy) / 2
            if numbers:
                label = (
                    ",".join(map(str, numbers))
                    if numbered_edges
                    else " / ".join(
                        edge.label
                        for edge in edges
                        if edge.src == src and edge.dst == dst and edge.label
                    )
                )
                box = draw.textbbox((0, 0), label, font=label_font)
                half_width = max(12, (box[2] - box[0]) / 2 + 5)
                draw.rounded_rectangle(
                    (mx - half_width, my - 12, mx + half_width, my + 12),
                    radius=11,
                    fill="white",
                    outline="black",
                )
                draw.text((mx, my), label, fill="black", font=label_font, anchor="mm")
        for ident, node in nodes.items():
            if visible_nodes is not None and ident not in visible_nodes:
                continue
            if display_labels and ident in display_labels:
                node = _Node(ident, display_labels[ident], node.shape)
            self._draw_node(draw, positions[ident], node, font)
        image.save(target, format="PNG", dpi=(144, 144))

    @staticmethod
    def _arrow(draw, sx, sy, dx, dy):
        import math

        angle = math.atan2(dy - sy, dx - sx)
        cosine, sine = abs(math.cos(angle)), abs(math.sin(angle))
        start_pad = end_pad = (
            min(
                _FLOW_NODE_WIDTH / 2 / cosine if cosine else float("inf"),
                _FLOW_NODE_HEIGHT / 2 / sine if sine else float("inf"),
            )
            + 4
        )
        x1, y1 = sx + math.cos(angle) * start_pad, sy + math.sin(angle) * start_pad
        x2, y2 = dx - math.cos(angle) * end_pad, dy - math.sin(angle) * end_pad
        draw.line((x1, y1, x2, y2), fill="black", width=2)
        size = 10
        left = (x2 - math.cos(angle - 0.55) * size, y2 - math.sin(angle - 0.55) * size)
        right = (x2 - math.cos(angle + 0.55) * size, y2 - math.sin(angle + 0.55) * size)
        draw.polygon([(x2, y2), left, right], fill="black")

    @staticmethod
    def _long_arrow(draw, sx, sy, dx, dy, width, height, horizontal):
        if horizontal:
            direction = 1 if dx > sx else -1
            lane = 20 if sy < height / 2 else height - 20
            start = sx + direction * (_FLOW_NODE_WIDTH / 2 + 4)
            end = dx - direction * (_FLOW_NODE_WIDTH / 2 + 4)
            first, last = start + direction * 14, end - direction * 14
            points = [(start, sy), (first, sy), (first, lane), (last, lane), (last, dy), (end, dy)]
            arrow = [(end, dy), (end - direction * 9, dy - 5), (end - direction * 9, dy + 5)]
            marker = (first, (sy + lane) / 2)
        else:
            direction = 1 if dy > sy else -1
            lane = 20 if sx < width / 2 else width - 20
            start = sy + direction * (_FLOW_NODE_HEIGHT / 2 + 4)
            end = dy - direction * (_FLOW_NODE_HEIGHT / 2 + 4)
            first, last = start + direction * 14, end - direction * 14
            points = [(sx, start), (sx, first), (lane, first), (lane, last), (dx, last), (dx, end)]
            arrow = [(dx, end), (dx - 5, end - direction * 9), (dx + 5, end - direction * 9)]
            marker = ((sx + lane) / 2, first)
        draw.line(points, fill="black", width=2)
        draw.polygon(arrow, fill="black")
        return marker

    @staticmethod
    def _wrap(draw, text: str, font, max_width: int = 205) -> list[str]:
        words = text.split()
        if not words:
            return [text]
        lines: list[str] = []
        cur = ""
        for word in words:
            while draw.textbbox((0, 0), word, font=font)[2] > max_width:
                if cur:
                    lines.append(cur)
                    cur = ""
                cut = 1
                while (
                    cut < len(word)
                    and draw.textbbox((0, 0), word[: cut + 1], font=font)[2] <= max_width
                ):
                    cut += 1
                lines.append(word[:cut])
                word = word[cut:]
            trial = (cur + " " + word).strip()
            if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def _draw_node(self, draw, pos, node: _Node, font):
        x, y = pos
        w, h = _FLOW_NODE_WIDTH, _FLOW_NODE_HEIGHT
        if node.shape == "diamond":
            draw.polygon(
                [(x, y - h / 2), (x + w / 2, y), (x, y + h / 2), (x - w / 2, y)],
                outline="black",
                fill="white",
            )
        elif node.shape == "circle":
            draw.ellipse(
                (x - h / 2, y - h / 2, x + h / 2, y + h / 2), outline="black", fill="white", width=2
            )
        elif node.shape == "round":
            draw.rounded_rectangle(
                (x - w / 2, y - h / 2, x + w / 2, y + h / 2),
                radius=18,
                outline="black",
                fill="white",
                width=2,
            )
        else:
            draw.rectangle(
                (x - w / 2, y - h / 2, x + w / 2, y + h / 2), outline="black", fill="white", width=2
            )
        text_width = 130 if node.shape == "diamond" else 100 if node.shape == "circle" else 210
        available_height = 65 if node.shape == "diamond" else 85 if node.shape == "circle" else 100
        for size in range(18, 11, -1):
            candidate = font if size == 18 else self._font(size)
            lines = self._wrap(draw, node.label, candidate, text_width)
            line_height = draw.textbbox((0, 0), "Ag", font=candidate)[3] + 3
            if len(lines) * line_height <= available_height:
                break
        else:
            raise MermaidRenderError("A flowchart node label is too long to render clearly.")
        yy = y - (len(lines) - 1) * line_height / 2
        for line in lines:
            draw.text((x, yy), line, fill="black", font=candidate, anchor="mm")
            yy += line_height

    def _render_sequence(self, lines: list[str], target: Path) -> None:
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise MermaidRenderError("Mermaid rendering requires Pillow.") from exc
        participants: dict[str, str] = {}
        messages: list[tuple[str, str, str, bool]] = []
        for line in lines[1:]:
            stripped = line.strip()
            pm = re.match(r"^participant\s+([\w.-]+)(?:\s+as\s+(.+))?$", stripped, flags=re.I)
            if pm:
                participants[pm.group(1)] = (pm.group(2) or pm.group(1)).strip()
                continue
            mm = re.match(
                r"^([A-Za-z_][\w.-]*?)\s*(-->>|->>|-->|->)\s*([A-Za-z_][\w.-]*)\s*:\s*(.+)$",
                stripped,
            )
            if mm:
                src, arrow, dst, text = mm.groups()
                participants.setdefault(src, src)
                participants.setdefault(dst, dst)
                messages.append((src, dst, text.strip(), arrow.startswith("--")))
        if not participants:
            raise MermaidRenderError("No supported Mermaid sequence participants were found.")
        if len(participants) > self.max_nodes or len(messages) > self.max_edges:
            raise MermaidRenderError(
                "Mermaid sequence exceeds configured participant/message limits."
            )
        ids = list(participants)
        width = max(700, 180 * len(ids) + 120)
        height = max(320, 150 + 72 * len(messages))
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        font = self._font(17)
        small = self._font(15)
        xs = {ident: 80 + i * (width - 160) / max(1, len(ids) - 1) for i, ident in enumerate(ids)}
        top = 55
        for ident in ids:
            x = xs[ident]
            label = participants[ident]
            draw.rounded_rectangle(
                (x - 65, top - 24, x + 65, top + 24),
                radius=8,
                outline="black",
                fill="white",
                width=2,
            )
            box = draw.textbbox((0, 0), label, font=font)
            draw.text((x - (box[2] - box[0]) / 2, top - 10), label, fill="black", font=font)
            draw.line((x, top + 24, x, height - 35), fill="gray", width=1)
        y = 125
        for src, dst, text, dashed in messages:
            x1, x2 = xs[src], xs[dst]
            if dashed:
                step = 10 if x2 >= x1 else -10
                xx = x1
                while xx < x2 if step > 0 else xx > x2:
                    end = xx + step * 0.55
                    draw.line((xx, y, end, y), fill="black", width=2)
                    xx += step
            else:
                draw.line((x1, y, x2, y), fill="black", width=2)
            direction = 1 if x2 >= x1 else -1
            draw.polygon(
                [(x2, y), (x2 - 10 * direction, y - 5), (x2 - 10 * direction, y + 5)], fill="black"
            )
            box = draw.textbbox((0, 0), text, font=small)
            tw = box[2] - box[0]
            draw.rectangle(
                ((x1 + x2) / 2 - tw / 2 - 3, y - 24, (x1 + x2) / 2 + tw / 2 + 3, y - 5),
                fill="white",
            )
            draw.text(((x1 + x2) / 2 - tw / 2, y - 23), text, fill="black", font=small)
            y += 72
        image.save(target, format="PNG", dpi=(144, 144))

    def _render_pie(self, lines: list[str], target: Path) -> None:
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise MermaidRenderError("Mermaid rendering requires Pillow.") from exc
        first = lines[0].strip()
        title_match = re.match(r"^pie(?:\s+title\s+(.+))?$", first, re.I)
        title = title_match.group(1).strip() if title_match and title_match.group(1) else ""
        values: list[tuple[str, float]] = []
        for line in lines[1:]:
            stripped = line.strip()
            tm = re.match(r"^title\s+(.+)$", stripped, re.I)
            if tm:
                title = tm.group(1).strip()
                continue
            m = re.match(r"^[\"']?(.+?)[\"']?\s*:\s*([0-9]+(?:\.[0-9]+)?)$", stripped)
            if m:
                values.append((m.group(1).strip(" \"'"), float(m.group(2))))
        if not values:
            raise MermaidRenderError("No supported Mermaid pie values were found.")
        image = Image.new("RGB", (900, 560), "white")
        draw = ImageDraw.Draw(image)
        font = self._font(18)
        title_font = self._font(24, bold=True)
        if title:
            draw.text((45, 25), title, fill="black", font=title_font)
        total = sum(v for _, v in values) or 1.0
        box = (55, 90, 455, 490)
        start = -90.0
        for idx, (_label, value) in enumerate(values):
            end = start + 360.0 * value / total
            shade = 220 - (idx * 31) % 150
            draw.pieslice(
                box, start=start, end=end, fill=(shade, shade, shade), outline="black", width=2
            )
            start = end
        y = 115
        for idx, (label, value) in enumerate(values):
            shade = 220 - (idx * 31) % 150
            draw.rectangle((520, y, 545, y + 20), fill=(shade, shade, shade), outline="black")
            draw.text((560, y - 2), f"{label}: {value:g}", fill="black", font=font)
            y += 42
        image.save(target, format="PNG", dpi=(144, 144))

    def _render_er(self, lines: list[str], target: Path) -> None:
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise MermaidRenderError("Mermaid rendering requires Pillow.") from exc
        relations: list[tuple[str, str, str, str]] = []
        relation_re = re.compile(r"^(\S+)\s+([|}{o*.+-]*--[|}{o*.+-]*)\s+(\S+)\s*(?::\s*(.*))?$")
        for line in lines[1:]:
            m = relation_re.match(line.strip())
            if m:
                left, cardinality, right, label = m.groups()
                relations.append((left, right, (label or "").strip(), cardinality))
        if not relations:
            raise MermaidRenderError("No supported Mermaid ER relationships were found.")
        if len(relations) > self.max_edges:
            raise MermaidRenderError("Mermaid ER diagram exceeds configured relationship limits.")
        width = 1050
        row_h = 72
        height = max(300, 120 + row_h * len(relations))
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        font = self._font(17)
        small = self._font(14)
        head = self._font(23, bold=True)
        draw.rounded_rectangle(
            (35, 25, width - 35, 72), radius=10, outline="black", fill=(245, 245, 245), width=2
        )
        draw.text((55, 37), "erDiagram", fill="black", font=head)
        y = 115
        for left, right, label, cardinality in relations:
            draw.rounded_rectangle(
                (55, y - 18, 330, y + 22), radius=7, outline="black", fill="white"
            )
            draw.text((70, y - 9), left, fill="black", font=font)
            draw.rounded_rectangle(
                (720, y - 18, 995, y + 22), radius=7, outline="black", fill="white"
            )
            draw.text((735, y - 9), right, fill="black", font=font)
            draw.line((350, y + 2, 700, y + 2), fill="black", width=2)
            draw.polygon([(700, y + 2), (687, y - 4), (687, y + 8)], fill="black")
            if cardinality:
                cbox = draw.textbbox((0, 0), cardinality, font=small)
                cw = cbox[2] - cbox[0]
                draw.rectangle((525 - cw / 2 - 5, y - 18, 525 + cw / 2 + 5, y + 1), fill="white")
                draw.text((525 - cw / 2, y - 17), cardinality, fill="black", font=small)
            if label:
                lbox = draw.textbbox((0, 0), label, font=small)
                lw = lbox[2] - lbox[0]
                draw.rectangle((525 - lw / 2 - 5, y + 5, 525 + lw / 2 + 5, y + 25), fill="white")
                draw.text((525 - lw / 2, y + 5), label, fill="black", font=small)
            y += row_h
        image.save(target, format="PNG", dpi=(144, 144))

    @staticmethod
    def _mindmap_label(text: str) -> str:
        text = text.strip()
        if text.lower().startswith("root"):
            text = text[4:].strip()
        for left, right in (("((", "))"), ("(", ")"), ("[", "]"), ("{", "}")):
            if text.startswith(left) and text.endswith(right):
                text = text[len(left) : -len(right)].strip()
                break
        return text or "root"

    def _render_mindmap(self, lines: list[str], target: Path) -> None:
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise MermaidRenderError("Mermaid rendering requires Pillow.") from exc
        nodes: list[tuple[int, str]] = []
        for raw in lines[1:]:
            if not raw.strip():
                continue
            expanded = raw.expandtabs(2)
            indent = len(expanded) - len(expanded.lstrip(" "))
            level = max(0, indent // 2)
            nodes.append((level, self._mindmap_label(expanded.strip())))
        if not nodes:
            raise MermaidRenderError("No supported Mermaid mindmap nodes were found.")
        if len(nodes) > self.max_nodes:
            raise MermaidRenderError("Mermaid mindmap exceeds configured node limits.")
        width = 1050
        row_h = 58
        height = max(320, 115 + row_h * len(nodes))
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        font = self._font(17)
        head = self._font(23, bold=True)
        draw.rounded_rectangle(
            (35, 25, width - 35, 72), radius=10, outline="black", fill=(245, 245, 245), width=2
        )
        draw.text((55, 37), "mindmap", fill="black", font=head)
        anchors: dict[int, tuple[float, float]] = {}
        y = 108
        for idx, (level, label) in enumerate(nodes):
            x = 65 + min(level, 3) * 250
            box_w = max(190, min(450, 26 + len(label) * 10))
            cy = y + 18
            if level > 0:
                parent = None
                for parent_level in range(level - 1, -1, -1):
                    if parent_level in anchors:
                        parent = anchors[parent_level]
                        break
                if parent:
                    px, py = parent
                    draw.line((px, py, x - 10, cy), fill=(90, 90, 90), width=2)
            draw.rounded_rectangle(
                (x, y, x + box_w, y + 36),
                radius=9,
                outline="black",
                fill="white",
                width=2 if level == 0 else 1,
            )
            draw.text((x + 12, y + 8), label[:70], fill="black", font=font)
            anchors[level] = (x + box_w, cy)
            for deeper in [k for k in anchors if k > level]:
                anchors.pop(deeper, None)
            y += row_h
        image.save(target, format="PNG", dpi=(144, 144))

    def _render_structured_text(self, lines: list[str], target: Path) -> None:
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise MermaidRenderError("Mermaid rendering requires Pillow.") from exc
        kind = lines[0].split(None, 1)[0]
        rows: list[str] = []
        for line in lines[1:]:
            stripped = line.strip()
            if not stripped or stripped.startswith("%%"):
                continue
            if stripped.lower().startswith(("title ", "section ")):
                rows.append(stripped.split(None, 1)[1].upper())
            else:
                rows.append(stripped)
        if not rows:
            raise MermaidRenderError(f"No supported Mermaid {kind} content was found.")
        if len(rows) > self.max_nodes + self.max_edges:
            raise MermaidRenderError("Mermaid diagram exceeds configured statement limits.")
        font = self._font(16)
        head = self._font(23, bold=True)
        width = 1050
        line_h = 38
        height = max(300, 100 + line_h * len(rows))
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (35, 25, width - 35, 72), radius=10, outline="black", fill=(245, 245, 245), width=2
        )
        draw.text((55, 37), kind, fill="black", font=head)
        y = 95
        rel_re = re.compile(
            r"\s*(?:\|\|--o\{|\}o--\|\||\}\|--\|\{|o\{--\|\{|<\|--|\*--|--\*|-->|->|--|\.\.)\s*"
        )
        for row in rows:
            if row.isupper() and len(row) < 80:
                draw.text((55, y), row, fill="black", font=self._font(17, bold=True))
            else:
                rel = rel_re.split(row, maxsplit=1)
                if len(rel) == 2 and rel[0] and rel[1]:
                    left, right = rel[0][:45], rel[1][:55]
                    draw.rounded_rectangle(
                        (55, y - 3, 330, y + 27), radius=7, outline="black", fill="white"
                    )
                    draw.text((67, y + 3), left, fill="black", font=font)
                    draw.line((345, y + 12, 620, y + 12), fill="black", width=2)
                    draw.polygon([(620, y + 12), (608, y + 6), (608, y + 18)], fill="black")
                    draw.rounded_rectangle(
                        (640, y - 3, 990, y + 27), radius=7, outline="black", fill="white"
                    )
                    draw.text((652, y + 3), right, fill="black", font=font)
                else:
                    draw.rounded_rectangle(
                        (55, y - 3, width - 55, y + 27),
                        radius=7,
                        outline=(120, 120, 120),
                        fill=(250, 250, 250),
                    )
                    draw.text((67, y + 3), row[:115], fill="black", font=font)
            y += line_h
        image.save(target, format="PNG", dpi=(144, 144))
