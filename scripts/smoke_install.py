"""Exercise a normal installed distribution in an empty workspace."""

from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from mddocx import Compiler, __version__, get_public_api_manifest, inspect_docx_bytes
from mddocx.doctor import run_doctor


def main() -> None:
    assert version("mddocx-native") == __version__
    assert get_public_api_manifest().api_version == "1"
    doctor = run_doctor()
    assert doctor.ok and doctor.mathjax_ready, doctor.to_text()
    assert doctor.svg_support == doctor.csl_support == "ready", doctor.to_text()

    with TemporaryDirectory() as folder:
        root = Path(folder)
        (root / "sample.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">'
            '<rect width="24" height="24" fill="blue"/></svg>',
            encoding="utf-8",
        )
        (root / "sample.md").write_text(
            "# Editable report\n\nবাংলা English. Equation $x^2$.\n\n![Blue box](sample.svg)\n\n"
            "<table><tr><th colspan='2'>Heading</th></tr><tr><td>1</td><td>2</td></tr></table>",
            encoding="utf-8",
        )
        command = [sys.executable, "-m", "mddocx", "sample.md", "--json"]
        report = json.loads(subprocess.check_output(command, cwd=root, text=True))
        assert report["status"] == "ok", report
        output = root / "sample.docx"
        inspection = inspect_docx_bytes(output.read_bytes())
        assert (
            inspection.ok and inspection.drawings == inspection.equations == inspection.tables == 1
        )
        result = Compiler().verify(root / "sample.md", output)
        assert result.ok, result.findings
    print(
        f"Installed mddocx {__version__}: MathJax, SVG, CSL, HTML tables, and verification passed"
    )


if __name__ == "__main__":
    main()
