from __future__ import annotations

import re
from xml.etree import ElementTree as ET

MATHML_NS = "http://www.w3.org/1998/Math/MathML"
ET.register_namespace("", MATHML_NS)
_ENVIRONMENT_TOKEN = re.compile(r"\\(?:(begin|end)\s*\{([^{}]+)\}|[A-Za-z]+|.)|[{}&]")
_ALIGN_PAIRS = {"alignedat", "alignat", "alignat*"}
_ALIGN_COLUMNS = _ALIGN_PAIRS | {"aligned", "align", "align*", "split"}
_OPTIONAL_ALIGNMENT = {"alignedat", "aligned", "gathered", "array"}
_TEXT_ESCAPE = re.compile(r"\\([&#%{}_$])")
_MATRIX_DELIMITERS = {
    "pmatrix": ("(", ")"),
    "bmatrix": ("[", "]"),
    "Bmatrix": ("{", "}"),
    "vmatrix": ("|", "|"),
    "Vmatrix": ("‖", "‖"),
    "cases": ("{", ""),
}
_MATRIX_ENVIRONMENTS = (
    {"array", "matrix", "smallmatrix", "gather", "gather*", "gathered"}
    | _ALIGN_COLUMNS
    | _MATRIX_DELIMITERS.keys()
)

GREEK = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "varepsilon": "ε",
    "zeta": "ζ",
    "eta": "η",
    "theta": "θ",
    "vartheta": "ϑ",
    "iota": "ι",
    "kappa": "κ",
    "lambda": "λ",
    "mu": "μ",
    "nu": "ν",
    "xi": "ξ",
    "omicron": "ο",
    "pi": "π",
    "varpi": "ϖ",
    "rho": "ρ",
    "varrho": "ϱ",
    "sigma": "σ",
    "varsigma": "ς",
    "tau": "τ",
    "upsilon": "υ",
    "phi": "φ",
    "varphi": "ϕ",
    "chi": "χ",
    "psi": "ψ",
    "omega": "ω",
    "Gamma": "Γ",
    "Delta": "Δ",
    "Theta": "Θ",
    "Lambda": "Λ",
    "Xi": "Ξ",
    "Pi": "Π",
    "Sigma": "Σ",
    "Upsilon": "Υ",
    "Phi": "Φ",
    "Psi": "Ψ",
    "Omega": "Ω",
}
SYMBOLS = {
    "pm": "±",
    "mp": "∓",
    "times": "×",
    "cdot": "·",
    "div": "÷",
    "le": "≤",
    "leq": "≤",
    "ge": "≥",
    "geq": "≥",
    "neq": "≠",
    "ne": "≠",
    "approx": "≈",
    "equiv": "≡",
    "infty": "∞",
    "partial": "∂",
    "nabla": "∇",
    "in": "∈",
    "notin": "∉",
    "subset": "⊂",
    "subseteq": "⊆",
    "supset": "⊃",
    "supseteq": "⊇",
    "cup": "∪",
    "cap": "∩",
    "to": "→",
    "rightarrow": "→",
    "leftarrow": "←",
    "leftrightarrow": "↔",
    "Rightarrow": "⇒",
    "Leftarrow": "⇐",
    "Leftrightarrow": "⇔",
    "forall": "∀",
    "exists": "∃",
    "neg": "¬",
    "land": "∧",
    "lor": "∨",
    "cdots": "⋯",
    "ldots": "…",
    "dots": "…",
    "vdots": "⋮",
    "ddots": "⋱",
    "prime": "′",
    "circ": "∘",
    "bullet": "•",
    "mid": "∣",
    "setminus": "∖",
    "hbar": "ℏ",
    "Longrightarrow": "⟹",
    "ni": "∋",
    "perp": "⊥",
    "parallel": "∥",
    "propto": "∝",
    "therefore": "∴",
    "because": "∵",
    "angle": "∠",
    "emptyset": "∅",
    "ell": "ℓ",
    "Re": "ℜ",
    "Im": "ℑ",
    "checkmark": "✓",
}
NARY = {"sum": "∑", "prod": "∏", "int": "∫", "iint": "∬", "iiint": "∭", "oint": "∮"}
FUNCTIONS = {
    "lim",
    "sin",
    "cos",
    "tan",
    "cot",
    "sec",
    "csc",
    "arcsin",
    "arccos",
    "arctan",
    "sinh",
    "cosh",
    "tanh",
    "log",
    "ln",
    "exp",
    "max",
    "min",
    "det",
    "gcd",
}
DELIMS = {
    "langle": "⟨",
    "rangle": "⟩",
    "lceil": "⌈",
    "rceil": "⌉",
    "lfloor": "⌊",
    "rfloor": "⌋",
    "lbrace": "{",
    "rbrace": "}",
    "vert": "|",
    "Vert": "‖",
}
ACCENTS = {
    "hat": "̂",
    "widehat": "̂",
    "bar": "̅",
    "overline": "̅",
    "vec": "⃗",
    "overrightarrow": "→",
    "tilde": "̃",
    "dot": "̇",
    "ddot": "̈",
}


class UnsupportedLatexError(ValueError):
    """Raised when the deterministic fallback cannot safely map a TeX command."""

    def __init__(self, command: str):
        self.command = command
        super().__init__(f"Unsupported LaTeX command: \\{command}")


def _e(tag: str, text: str | None = None, *children: ET.Element, **attrs: str) -> ET.Element:
    el = ET.Element(f"{{{MATHML_NS}}}{tag}", attrs)
    if text is not None:
        el.text = text
    for child in children:
        el.append(child)
    return el


class BasicLatexToMathML:
    """Deterministic non-executing LaTeX subset parser for Word-native math.

    It covers the Phase-2 regression surface, not arbitrary TeX macro expansion.
    """

    def convert(self, latex: str) -> str:
        parser = _Parser(latex)
        children = parser.parse_sequence()
        if parser.i < len(parser.text):
            raise ValueError(f"Unexpected LaTeX at offset {parser.i}")
        math = _e("math", None, *children)
        return ET.tostring(math, encoding="unicode")


class _Parser:
    def __init__(self, text: str):
        self.text = text.strip()
        self.i = 0

    def parse_sequence(self, stop: str | None = None) -> list[ET.Element]:
        out: list[ET.Element] = []
        while self.i < len(self.text):
            if stop and self.text.startswith(stop, self.i):
                self.i += len(stop)
                return out
            ch = self.text[self.i]
            if ch.isspace():
                self.i += 1
                continue
            if ch == "}":
                if stop == "}":
                    self.i += 1
                    return out
                raise ValueError("Unexpected '}' in LaTeX expression")
            base = self.parse_atom()
            sub = sup = None
            self._skip_spaces()
            while self.i < len(self.text) and self.text[self.i] in "_^":
                op = self.text[self.i]
                self.i += 1
                arg = self.parse_script_arg()
                if op == "_":
                    sub = arg
                else:
                    sup = arg
                self._skip_spaces()

            # In TeX, a script written after a closing delimiter applies visually to
            # the delimited expression, e.g. ``E[X]^2`` or ``(x+1)^n``.  Emitting
            # OMML with only the closing bracket as the superscript base is fragile
            # in Word-compatible hosts, so group the matching delimiter pair first.
            if sub is not None or sup is not None:
                close = base.text if base.tag.endswith("}mo") else None
                opener = {")": "(", "]": "["}.get(close or "")
                if opener is not None:
                    depth = 0
                    match = None
                    for idx in range(len(out) - 1, -1, -1):
                        candidate = out[idx]
                        if not candidate.tag.endswith("}mo"):
                            continue
                        value = candidate.text or ""
                        if value == close:
                            depth += 1
                        elif value == opener:
                            if depth == 0:
                                match = idx
                                break
                            depth -= 1
                    if match is not None:
                        grouped = out[match:] + [base]
                        del out[match:]
                        base = _e("mrow", None, *grouped)

            if sub is not None and sup is not None:
                base = _e("msubsup", None, base, sub, sup)
            elif sub is not None:
                base = _e("msub", None, base, sub)
            elif sup is not None:
                base = _e("msup", None, base, sup)
            out.append(base)
        if stop:
            raise ValueError(f"Unclosed LaTeX group, expected {stop!r}")
        return out

    def parse_script_arg(self) -> ET.Element:
        self._skip_spaces()
        if self.i < len(self.text) and self.text[self.i] == "{":
            return self.parse_group()
        return self.parse_atom()

    def parse_required_arg(self) -> ET.Element:
        self._skip_spaces()
        if self.i >= len(self.text):
            raise ValueError("Expected LaTeX argument")
        ch = self.text[self.i]
        if ch == "{":
            return self.parse_group()
        # Unbraced TeX macro arguments are one token, not a whole numeric word.
        if ch.isdigit():
            self.i += 1
            return _e("mn", ch)
        if ch.isalpha():
            self.i += 1
            return _e("mi", ch)
        return self.parse_atom()

    def parse_group(self) -> ET.Element:
        self._skip_spaces()
        if self.i >= len(self.text) or self.text[self.i] != "{":
            raise ValueError("Expected '{' in LaTeX expression")
        self.i += 1
        items = self.parse_sequence("}")
        return items[0] if len(items) == 1 else _e("mrow", None, *items)

    def _read_braced_raw(self) -> str:
        self._skip_spaces()
        if self.i >= len(self.text) or self.text[self.i] != "{":
            raise ValueError("Expected braced argument")
        self.i += 1
        start = self.i
        depth = 1
        while self.i < len(self.text):
            if self.text[self.i] == "\\":
                self.i += 2
                continue
            if self.text[self.i] == "{":
                depth += 1
            elif self.text[self.i] == "}":
                depth -= 1
                if depth == 0:
                    raw = self.text[start : self.i]
                    self.i += 1
                    return raw
            self.i += 1
        raise ValueError("Unclosed braced argument")

    def _read_bracket_raw(self) -> str | None:
        self._skip_spaces()
        if self.i >= len(self.text) or self.text[self.i] != "[":
            return None
        self.i += 1
        start = self.i
        depth = 1
        while self.i < len(self.text):
            if self.text[self.i] == "[":
                depth += 1
            elif self.text[self.i] == "]":
                depth -= 1
                if depth == 0:
                    raw = self.text[start : self.i]
                    self.i += 1
                    return raw
            self.i += 1
        raise ValueError("Unclosed optional argument")

    def parse_atom(self) -> ET.Element:
        if self.i >= len(self.text):
            raise ValueError("Expected LaTeX atom")
        ch = self.text[self.i]
        if ch == "{":
            return self.parse_group()
        if ch == "\\":
            return self.parse_command()
        if ch in "([|":
            self.i += 1
            return _e("mo", ch)
        if ch in ")]":
            self.i += 1
            return _e("mo", ch)
        if ch.isdigit() or (
            ch == "." and self.i + 1 < len(self.text) and self.text[self.i + 1].isdigit()
        ):
            start = self.i
            if ch == ".":
                self.i += 1
            while self.i < len(self.text) and self.text[self.i].isdigit():
                self.i += 1
            if (
                self.i < len(self.text)
                and self.text[self.i] == "."
                and self.i + 1 < len(self.text)
                and self.text[self.i + 1].isdigit()
            ):
                self.i += 1
                while self.i < len(self.text) and self.text[self.i].isdigit():
                    self.i += 1
            return _e("mn", self.text[start : self.i])
        if ch.isalpha():
            self.i += 1
            return _e("mi", ch)
        self.i += 1
        return _e("mo", ch)

    def parse_command(self) -> ET.Element:
        self.i += 1
        if self.i >= len(self.text):
            return _e("mo", "\\")
        if not self.text[self.i].isalpha():
            cmd = self.text[self.i]
            self.i += 1
            if cmd in {",", ";", ":", "!", " "}:
                return _e("mspace", None, width="0.2em")
            if cmd == "\\":
                return _e("mspace", None, linebreak="newline")
            if cmd in "{}|":
                return _e("mo", cmd)
            return _e("mo", cmd)

        start = self.i
        while self.i < len(self.text) and self.text[self.i].isalpha():
            self.i += 1
        cmd = self.text[start : self.i]

        if cmd in {"frac", "dfrac", "tfrac"}:
            return _e("mfrac", None, self.parse_required_arg(), self.parse_required_arg())
        if cmd == "binom":
            fraction = _e(
                "mfrac",
                None,
                self.parse_required_arg(),
                self.parse_required_arg(),
                linethickness="0",
            )
            return _e("mfenced", None, fraction, open="(", close=")")
        if cmd == "sqrt":
            degree = self._read_bracket_raw()
            radicand = self.parse_required_arg()
            if degree is None:
                return _e("msqrt", None, radicand)
            deg_parser = _Parser(degree)
            deg_items = deg_parser.parse_sequence()
            deg = deg_items[0] if len(deg_items) == 1 else _e("mrow", None, *deg_items)
            return _e("mroot", None, radicand, deg)
        if cmd == "left":
            return self._parse_left_right()
        if cmd == "right":
            raise ValueError("Unexpected \\right")
        if cmd == "begin":
            return self._parse_environment(self._read_braced_raw())
        if cmd == "end":
            raise ValueError("Unexpected \\end")
        if cmd in {
            "mathrm",
            "mathbf",
            "mathit",
            "mathsf",
            "mathtt",
            "mathbb",
            "mathcal",
            "mathfrak",
            "operatorname",
            "textrm",
            "textnormal",
            "textbf",
            "textit",
        }:
            variants = {
                "mathrm": "normal",
                "operatorname": "normal",
                "mathbf": "bold",
                "mathit": "italic",
                "mathsf": "sans-serif",
                "mathtt": "monospace",
                "mathbb": "double-struck",
                "mathcal": "script",
                "mathfrak": "fraktur",
                "textrm": "normal",
                "textnormal": "normal",
                "textbf": "bold",
                "textit": "italic",
            }
            return _e("mstyle", None, self.parse_required_arg(), mathvariant=variants[cmd])
        if cmd == "boxed":
            return _e("menclose", None, self.parse_required_arg(), notation="box")
        if cmd == "text":
            return _e("mtext", _TEXT_ESCAPE.sub(r"\1", self._read_braced_raw()))
        if cmd in ACCENTS:
            base = self.parse_required_arg()
            return _e("mover", None, base, _e("mo", ACCENTS[cmd]), accent="true")
        if cmd in GREEK:
            return _e("mi", GREEK[cmd])
        if cmd in NARY:
            return _e("mo", NARY[cmd], largeop="true")
        if cmd in SYMBOLS:
            return _e("mo", SYMBOLS[cmd])
        if cmd in DELIMS:
            return _e("mo", DELIMS[cmd])
        if cmd in FUNCTIONS:
            return _e("mi", cmd, mathvariant="normal")
        if cmd in {"quad", "qquad"}:
            return _e("mspace", None, width="1em" if cmd == "quad" else "2em")
        if cmd in {"displaystyle", "textstyle", "scriptstyle", "scriptscriptstyle"}:
            return _e("mspace", None, width="0em")
        if cmd == "mod":
            return _e("mtext", " mod ")
        if cmd == "pmod":
            return _e("mfenced", None, _e("mtext", "mod "), self.parse_required_arg())
        if cmd == "tag":
            # Equation numbering remains editable math. Word will display the tag
            # on the same equation line even though it is not a SEQ field.
            return _e(
                "mrow",
                None,
                _e("mspace", None, width="1em"),
                _e("mfenced", None, self.parse_required_arg(), open="(", close=")"),
            )
        if cmd == "limits" or cmd == "nolimits":
            return _e("mspace", None, width="0em")
        raise UnsupportedLatexError(cmd)

    def _parse_left_right(self) -> ET.Element:
        open_delim = self._read_delimiter()
        content_start = self.i
        depth = 1
        pos = self.i
        while pos < len(self.text):
            if self.text.startswith("\\left", pos):
                depth += 1
                pos += 5
                continue
            if self.text.startswith("\\right", pos):
                depth -= 1
                if depth == 0:
                    inner = self.text[content_start:pos]
                    self.i = pos + len("\\right")
                    close_delim = self._read_delimiter()
                    parser = _Parser(inner)
                    items = parser.parse_sequence()
                    body = items[0] if len(items) == 1 else _e("mrow", None, *items)
                    return _e("mfenced", None, body, open=open_delim, close=close_delim)
                pos += 6
                continue
            pos += 1
        raise ValueError("Unclosed \\left delimiter")

    def _read_delimiter(self) -> str:
        self._skip_spaces()
        if self.i >= len(self.text):
            raise ValueError("Expected delimiter")
        if self.text[self.i] == "\\":
            self.i += 1
            start = self.i
            while self.i < len(self.text) and self.text[self.i].isalpha():
                self.i += 1
            if start == self.i and self.i < len(self.text):
                ch = self.text[self.i]
                self.i += 1
                return ch
            cmd = self.text[start : self.i]
            return DELIMS.get(cmd, SYMBOLS.get(cmd, cmd))
        ch = self.text[self.i]
        self.i += 1
        return "" if ch == "." else ch

    def _parse_environment(self, env: str) -> ET.Element:
        grid = env in _MATRIX_ENVIRONMENTS
        if not grid and env not in {"equation", "equation*"}:
            raise ValueError(f"Unsupported LaTeX environment: {env}")
        baseline = self._read_bracket_raw() if env in _OPTIONAL_ALIGNMENT else None
        align = {"t": "top", "b": "bottom", "c": "center"}.get(
            "c" if baseline is None else baseline.strip()
        )
        if align is None:
            raise ValueError(f"Invalid vertical alignment for LaTeX environment: {env}")
        alignments: list[str] = []
        if env in _ALIGN_PAIRS:
            pairs = self._read_braced_raw().strip()
            if not re.fullmatch(r"[1-9][0-9]?", pairs) or int(pairs) > 32:
                raise ValueError("alignedat requires 1 to 32 alignment pairs for Word.")
            alignments = ["right", "left"] * int(pairs)
        if env == "array":
            spec = "".join(self._read_braced_raw().split())
            if not re.fullmatch(r"[lcr]{1,64}", spec):
                raise ValueError("Word fallback supports up to 64 l/c/r array columns.")
            alignments = [{"l": "left", "c": "center", "r": "right"}[column] for column in spec]

        rows = self._environment_rows(env, grid=grid)
        if not grid:
            items = _Parser(rows[0][0]).parse_sequence()
            return items[0] if len(items) == 1 else _e("mrow", None, *items)

        width = max(map(len, rows), default=0)
        if width > 64:
            raise ValueError("Word supports up to 64 columns in a native equation matrix.")
        if alignments and width > len(alignments):
            raise ValueError(f"Too many alignment columns for {env}.")
        if env in _ALIGN_COLUMNS and not alignments:
            alignments = ["right" if index % 2 == 0 else "left" for index in range(width)]
        if env == "cases":
            alignments = ["left"]
        mrows: list[ET.Element] = []
        for cells in rows:
            if env in _ALIGN_PAIRS or env == "array":
                cells.extend([""] * (len(alignments) - len(cells)))
            mtds = []
            for cell in cells:
                parser = _Parser(cell.strip())
                items = parser.parse_sequence()
                cell_node = items[0] if len(items) == 1 else _e("mrow", None, *items)
                mtds.append(_e("mtd", None, cell_node))
            mrows.append(_e("mtr", None, *mtds))
        table = _e(
            "mtable",
            None,
            *mrows,
            columnalign=" ".join(alignments) or "center",
            align=align,
        )
        if env not in _MATRIX_DELIMITERS:
            return table
        opening, closing = _MATRIX_DELIMITERS[env]
        return _e("mfenced", None, table, open=opening, close=closing)

    def _environment_rows(self, env: str, *, grid: bool) -> list[list[str]]:
        rows: list[list[str]] = []
        cells: list[str] = []
        nested: list[str] = []
        depth = 0
        start = self.i
        for match in _ENVIRONMENT_TOKEN.finditer(self.text, start):
            token, directive, name = match[0], match[1], match[2]
            if directive == "begin":
                nested.append(name.strip())
            elif directive == "end":
                closing = name.strip()
                if nested:
                    if nested.pop() != closing:
                        raise ValueError(f"Mismatched LaTeX environment: {closing}")
                elif closing == env and depth == 0:
                    cells.append(self.text[start : match.start()])
                    self.i = match.end()
                    if len(cells) > 1 or cells[0].strip() or not grid:
                        rows.append(cells)
                    return rows
                else:
                    raise ValueError(f"Mismatched LaTeX environment: {closing}")
            elif token == "{":
                depth += 1
            elif token == "}":
                depth -= 1
                if depth < 0:
                    raise ValueError(f"Unexpected closing brace in {env}.")
            elif grid and depth == 0 and not nested and token in {"&", r"\\"}:
                cells.append(self.text[start : match.start()])
                start = match.end()
                if token == r"\\":
                    rows.append(cells)
                    cells = []
        raise ValueError(f"Unclosed LaTeX environment: {env}")

    def _skip_spaces(self) -> None:
        while self.i < len(self.text) and self.text[self.i].isspace():
            self.i += 1
