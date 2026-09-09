# Extension API

Phase 3 exposes extension hooks without placing renderer objects inside the canonical AST.
Extensions are supplied through `RenderConfig(extensions=(...))` and may implement any subset of
these hooks:

- `configure_markdown(markdown_it)` — configure markdown-it before parsing;
- `parse_block(parser, tokens, index)` — consume a block token and return `(node, next_index)`;
- `parse_inline(parser, tokens, index)` — consume an inline token and return `(node, next_index)`;
- `transform_document(document)` — normalize/augment the canonical AST after parsing;
- `transform_layout(document, plan)` — return an updated immutable, versioned `LayoutPlan`;
- `render_block(renderer, node)` — render a custom block AST node and return `True` when handled;
- `render_inline(renderer, paragraph, node, state)` — render a custom inline node and return `True`.

Parsing hooks must advance the token index. New extensions should implement the public
`AstTransformExtension` and/or `LayoutTransformExtension` protocols, which operate on the
versioned canonical AST and `LAYOUT_SCHEMA_VERSION`. Returned values are validated before
rendering; transform failures use stable `PLUGIN405`–`PLUGIN408` diagnostics, while an
incompatible returned layout schema uses `PLUGIN409`.

The renderer hooks remain available for v1 compatibility, but they expose implementation details
and are not the preferred v2 integration boundary. Extensions that still require custom OOXML
should keep it localized and must not place `python-docx` objects inside the canonical AST.

## Custom AST example

```python
from dataclasses import dataclass
from mddocx import MarkdownWord, RenderConfig
from mddocx.ast.base import Document, Node

@dataclass(slots=True)
class Callout(Node):
    text: str = ""

class CalloutExtension:
    def render_block(self, renderer, node):
        if not isinstance(node, Callout):
            return False
        paragraph = renderer.document.add_paragraph(style="MD Quote")
        paragraph.add_run(node.text)
        return True

converter = MarkdownWord(RenderConfig(extensions=(CalloutExtension(),)))
blob = converter.render_ast(Document(children=[Callout(text="Important")]))
```

Unrecognized custom nodes are not silently discarded: the renderer emits `EXT301` diagnostics.
