from __future__ import annotations

from docx.oxml import OxmlElement

from mddocx.diagnostics import Diagnostic, MddocxError
from mddocx.ooxml.text import clean_xml_text

from .context import RenderContext


class NativeMathRenderer:
    """Render editable OMML equations with explicit fallback diagnostics."""

    def __init__(self, context: RenderContext) -> None:
        self.context = context

    def append(self, paragraph, latex: str, *, display: bool, source=None) -> None:
        try:
            omath = self.context.math.latex_to_omml(latex, display)
            if display:
                math_paragraph = OxmlElement("m:oMathPara")
                math_paragraph.append(omath)
                paragraph._p.append(math_paragraph)
            else:
                paragraph._p.append(omath)
        except Exception as exc:
            mode = self.context.config.math_failure.mode
            diagnostic = Diagnostic(
                "error" if mode == "error" else "warning",
                "MATH201",
                f"Unable to convert LaTeX equation with {self.context.math.engine_name}: {exc}",
                getattr(source, "file", None),
                getattr(source, "line", None),
                "Run 'mddocx math-check' to locate unsupported TeX; simplify the expression or install the math extra.",
            )
            if mode == "error":
                raise MddocxError(diagnostic) from exc
            self.context.reporter.diagnostics.append(diagnostic)
            paragraph.add_run(clean_xml_text(latex))
