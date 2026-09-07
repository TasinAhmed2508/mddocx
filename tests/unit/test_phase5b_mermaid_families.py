from pathlib import Path
import pytest
from PIL import Image

from mddocx.diagrams import MermaidRenderer


CASES = [
    """stateDiagram-v2\n[*] --> Ready\nReady --> Running\n""",
    """classDiagram\nAnimal <|-- Duck\nDuck : +swim()\n""",
    """erDiagram\nCUSTOMER ||--o{ ORDER : places\n""",
    """mindmap\nroot((Compiler))\n  Parser\n  Renderer\n""",
    """timeline\ntitle Release history\n2025 : v0.5\n2026 : v0.6\n""",
    """journey\ntitle User journey\nsection Convert\nWrite Markdown: 5: User\nRender DOCX: 4: User\n""",
    """gantt\ntitle Release\nsection Work\nParser :a1, 2026-01-01, 5d\nRenderer :after a1, 5d\n""",
    """pie title Languages\n\"Python\" : 70\n\"XML\" : 30\n""",
]


@pytest.mark.parametrize("source", CASES)
def test_advanced_mermaid_family_renders_offline(tmp_path, source):
    path = MermaidRenderer().render(source, tmp_path)
    assert path.exists()
    with Image.open(path) as image:
        assert image.width >= 600
        assert image.height >= 300
