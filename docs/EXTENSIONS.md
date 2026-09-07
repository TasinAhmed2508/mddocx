# Extension API

Phase 3 exposes extension hooks without placing renderer objects inside the canonical AST.
Extensions are supplied through `RenderConfig(extensions=(...))` and may implement any subset of
these hooks:

- `configure_markdown(markdown_it)` — configure markdown-it before parsing;
- `parse_block(parser, tokens, index)` — consume a block token and return `(node, next_index)`;
- `parse_inline(parser, tokens, index)` — consume an inline token and return `(node, next_index)`;
- `transform_document(document)` — normalize/augment the canonical AST after parsing;
- `render_block(renderer, node)` — render a custom block AST node and return `True` when handled;
- `render_inline(renderer, paragraph, node, state)` — render a custom inline node and return `True`.

Parsing hooks must advance the token index. Render hooks should use the renderer's current Word
`document` and should keep custom OOXML localized to the extension instead of mutating parser
objects with `python-docx` state.

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
