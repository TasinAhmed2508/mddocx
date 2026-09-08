from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re


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
            (r"^\{(.*)\}$", "diamond"),
            (r"^\[(.*)\]$", "rect"),
            (r'^\("(.*)"\)$', "round"),
            (r"^\((.*)\)$", "round"),
        ]
        for pattern, shape in patterns:
            m = re.match(pattern, suffix)
            if m:
                return _Node(ident, m.group(1).strip() or ident, shape)
        return _Node(ident, ident)

    def _parse_flow(self, lines: list[str]):
        head = re.match(r"^(?:flowchart|graph)\s+([A-Za-z]+)", lines[0], flags=re.I)
        direction = head.group(1).upper() if head else "TD"
        nodes: dict[str, _Node] = {}
        edges: list[_Edge] = []
        edge_re = re.compile(r"\s+(-->|---|-.->|==>)\s+")
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
            parts = edge_re.split(stripped)
            if len(parts) >= 3:
                current = self._node_from_token(parts[0])
                nodes[current.ident] = (
                    current
                    if current.label != current.ident or current.ident not in nodes
                    else nodes[current.ident]
                )
                idx = 1
                while idx + 1 < len(parts):
                    nxt = self._node_from_token(parts[idx + 1])
                    nodes[nxt.ident] = (
                        nxt
                        if nxt.label != nxt.ident or nxt.ident not in nodes
                        else nodes[nxt.ident]
                    )
                    edges.append(_Edge(current.ident, nxt.ident))
                    current = nxt
                    idx += 2
                continue
            try:
                node = self._node_from_token(stripped)
            except MermaidRenderError:
                continue
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

    def _render_flowchart(self, lines: list[str], target: Path) -> None:
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise MermaidRenderError("Mermaid rendering requires Pillow.") from exc
        direction, nodes, edges = self._parse_flow(lines)
        levels = self._levels(nodes, edges)
        horizontal = direction in {"LR", "RL"}
        layer_gap, item_gap = 190, 220
        margin = 70
        max_items = max(len(level) for level in levels)
        if horizontal:
            width = margin * 2 + max(1, len(levels) - 1) * layer_gap + 220
            height = margin * 2 + max(1, max_items - 1) * 110 + 90
        else:
            width = margin * 2 + max(1, max_items - 1) * item_gap + 220
            height = margin * 2 + max(1, len(levels) - 1) * 150 + 90
        width, height = max(600, width), max(320, height)
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        font = self._font(18)
        label_font = self._font(15)
        positions: dict[str, tuple[float, float]] = {}
        for li, level in enumerate(levels):
            for ni, ident in enumerate(level):
                if horizontal:
                    x = margin + 110 + li * layer_gap
                    y = height / 2 + (ni - (len(level) - 1) / 2) * 110
                else:
                    x = width / 2 + (ni - (len(level) - 1) / 2) * item_gap
                    y = margin + 45 + li * 150
                positions[ident] = (x, y)
        if direction in {"RL", "BT"}:
            if horizontal:
                positions = {n: (width - x, y) for n, (x, y) in positions.items()}
            else:
                positions = {n: (x, height - y) for n, (x, y) in positions.items()}

        for edge in edges:
            if edge.src not in positions or edge.dst not in positions:
                continue
            sx, sy = positions[edge.src]
            dx, dy = positions[edge.dst]
            self._arrow(draw, sx, sy, dx, dy)
            if edge.label:
                mx, my = (sx + dx) / 2, (sy + dy) / 2
                box = draw.textbbox((0, 0), edge.label, font=label_font)
                tw, th = box[2] - box[0], box[3] - box[1]
                draw.rectangle(
                    (mx - tw / 2 - 4, my - th / 2 - 3, mx + tw / 2 + 4, my + th / 2 + 3),
                    fill="white",
                )
                draw.text((mx - tw / 2, my - th / 2), edge.label, fill="black", font=label_font)
        for ident, node in nodes.items():
            self._draw_node(draw, positions[ident], node, font)
        image.save(target, format="PNG", dpi=(144, 144))

    @staticmethod
    def _arrow(draw, sx, sy, dx, dy):
        import math

        angle = math.atan2(dy - sy, dx - sx)
        start_pad, end_pad = 70, 70
        x1, y1 = sx + math.cos(angle) * start_pad, sy + math.sin(angle) * start_pad
        x2, y2 = dx - math.cos(angle) * end_pad, dy - math.sin(angle) * end_pad
        draw.line((x1, y1, x2, y2), fill="black", width=2)
        size = 10
        left = (x2 - math.cos(angle - 0.55) * size, y2 - math.sin(angle - 0.55) * size)
        right = (x2 - math.cos(angle + 0.55) * size, y2 - math.sin(angle + 0.55) * size)
        draw.polygon([(x2, y2), left, right], fill="black")

    @staticmethod
    def _wrap(draw, text: str, font, max_width: int = 155) -> list[str]:
        words = text.split()
        if not words:
            return [text]
        lines: list[str] = []
        cur = words[0]
        for word in words[1:]:
            trial = cur + " " + word
            if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        return lines

    def _draw_node(self, draw, pos, node: _Node, font):
        x, y = pos
        w, h = (180, 74) if node.shape != "circle" else (88, 88)
        if node.shape == "diamond":
            draw.polygon(
                [(x, y - 48), (x + 95, y), (x, y + 48), (x - 95, y)], outline="black", fill="white"
            )
        elif node.shape == "circle":
            draw.ellipse((x - 44, y - 44, x + 44, y + 44), outline="black", fill="white", width=2)
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
        lines = self._wrap(draw, node.label, font)
        heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
        total_h = sum(heights) + max(0, len(lines) - 1) * 3
        yy = y - total_h / 2
        for line, th in zip(lines, heights):
            box = draw.textbbox((0, 0), line, font=font)
            tw = box[2] - box[0]
            draw.text((x - tw / 2, yy), line, fill="black", font=font)
            yy += th + 3

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
