from __future__ import annotations

from typing import Any, Protocol


class MddocxExtension(Protocol):
    """Optional hook interface for custom Markdown/AST/render behavior.

    Extensions may implement any subset of these methods. Parsing hooks return
    ``(node, next_index)`` when they consume a token, otherwise ``None``.
    Render hooks return ``True`` when the node was handled.
    """

    def configure_markdown(self, markdown_it: Any) -> None: ...
    def parse_block(self, parser: Any, tokens: list[Any], index: int) -> tuple[Any, int] | None: ...
    def parse_inline(self, parser: Any, tokens: list[Any], index: int) -> tuple[Any, int] | None: ...
    def transform_document(self, document: Any) -> Any: ...
    def render_block(self, renderer: Any, node: Any) -> bool: ...
    def render_inline(self, renderer: Any, paragraph: Any, node: Any, state: dict[str, Any]) -> bool: ...


def call_configure_markdown(extensions: tuple[Any, ...], markdown_it: Any) -> None:
    for extension in extensions:
        hook = getattr(extension, "configure_markdown", None)
        if hook is not None:
            hook(markdown_it)


def parse_custom_block(extensions: tuple[Any, ...], parser: Any, tokens: list[Any], index: int):
    for extension in extensions:
        hook = getattr(extension, "parse_block", None)
        if hook is not None:
            result = hook(parser, tokens, index)
            if result is not None:
                node, next_index = result
                if next_index <= index:
                    raise ValueError("Extension parse_block() must advance the token index.")
                return node, next_index
    return None


def parse_custom_inline(extensions: tuple[Any, ...], parser: Any, tokens: list[Any], index: int):
    for extension in extensions:
        hook = getattr(extension, "parse_inline", None)
        if hook is not None:
            result = hook(parser, tokens, index)
            if result is not None:
                node, next_index = result
                if next_index <= index:
                    raise ValueError("Extension parse_inline() must advance the token index.")
                return node, next_index
    return None


def call_transform_document(extensions: tuple[Any, ...], document: Any) -> Any:
    current = document
    for extension in extensions:
        hook = getattr(extension, "transform_document", None)
        if hook is not None:
            updated = hook(current)
            if updated is not None:
                current = updated
    return current


def render_custom_block(extensions: tuple[Any, ...], renderer: Any, node: Any) -> bool:
    for extension in extensions:
        hook = getattr(extension, "render_block", None)
        if hook is not None and hook(renderer, node):
            return True
    return False


def render_custom_inline(
    extensions: tuple[Any, ...], renderer: Any, paragraph: Any, node: Any, state: dict[str, Any]
) -> bool:
    for extension in extensions:
        hook = getattr(extension, "render_inline", None)
        if hook is not None and hook(renderer, paragraph, node, state):
            return True
    return False
