from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any

from .ast.base import Node
from .ast.block import ImageBlock, MathBlock, TableCell
from .ast.inline import Image, InlineMath
from .config import CompilationLimits
from .diagnostics import Diagnostic, MddocxError


def enforce_input_limit(markdown: str, limits: CompilationLimits) -> None:
    size = len(markdown.encode("utf-8"))
    if size > limits.max_input_bytes:
        raise MddocxError(
            Diagnostic(
                "error", "LIMIT401", f"Markdown input exceeds {limits.max_input_bytes} bytes."
            )
        )


def enforce_ast_limits(document: Node, limits: CompilationLimits) -> None:
    counts = {"nodes": 0, "table_cells": 0, "images": 0, "equations": 0}

    def visit(value: Any, depth: int) -> None:
        if depth > limits.max_nesting_depth:
            raise MddocxError(
                Diagnostic(
                    "error", "LIMIT403", f"AST nesting exceeds {limits.max_nesting_depth} levels."
                )
            )
        if isinstance(value, Node):
            counts["nodes"] += 1
            if counts["nodes"] > limits.max_ast_nodes:
                raise MddocxError(
                    Diagnostic("error", "LIMIT402", f"AST exceeds {limits.max_ast_nodes} nodes.")
                )
            if isinstance(value, TableCell):
                counts["table_cells"] += 1
                if counts["table_cells"] > limits.max_table_cells:
                    raise MddocxError(
                        Diagnostic(
                            "error",
                            "LIMIT404",
                            f"Document exceeds {limits.max_table_cells} table cells.",
                        )
                    )
            if isinstance(value, (ImageBlock, Image)):
                counts["images"] += 1
                if counts["images"] > limits.max_images:
                    raise MddocxError(
                        Diagnostic(
                            "error", "LIMIT405", f"Document exceeds {limits.max_images} images."
                        )
                    )
            if isinstance(value, (MathBlock, InlineMath)):
                counts["equations"] += 1
                if counts["equations"] > limits.max_equations:
                    raise MddocxError(
                        Diagnostic(
                            "error",
                            "LIMIT406",
                            f"Document exceeds {limits.max_equations} equations.",
                        )
                    )
            if is_dataclass(value):
                for f in fields(value):
                    if f.name == "source":
                        continue
                    visit(getattr(value, f.name), depth + 1)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item, depth + 1)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item, depth + 1)

    visit(document, 0)
