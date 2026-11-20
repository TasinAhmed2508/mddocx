"""Bounded expansion of leading, equation-local LaTeX newcommand definitions."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import re

from .latex import UnsupportedLatexError

_TOKEN = re.compile(r"\\[A-Za-z]+|\\[\s\S]|#[1-9]|\s+|[\s\S]")
_CONTROL_WORD = re.compile(r"\\[A-Za-z]+")
_MAX_EXPANSIONS = 1000
_MAX_EXPANSION_CHARS = 100_000


@dataclass(frozen=True, slots=True)
class _Macro:
    count: int
    default: list[str] | None
    body: list[str]


def expand_newcommands(tex: str) -> str:
    """Expand leading declarations before either renderer or source validation."""
    if not tex.startswith(r"\newcommand"):
        return tex
    if len(tex) > _MAX_EXPANSION_CHARS:
        raise UnsupportedLatexError("equation-local macro input exceeds the length limit")
    tokens = deque(_TOKEN.findall(tex))
    macros: dict[str, _Macro] = {}
    # Comments, nested declarations, and verbatim text need the original TeX parser.
    if any(
        token
        in {
            "%",
            r"\def",
            r"\gdef",
            r"\edef",
            r"\xdef",
            r"\renewcommand",
            r"\providecommand",
            r"\newenvironment",
            r"\DeclareMathOperator",
            r"\let",
            r"\verb",
        }
        for token in tokens
    ):
        return tex
    try:
        while tokens and tokens[0] == r"\newcommand":
            tokens.popleft()
            name = "".join(_argument(tokens)).strip()
            count_text = _optional(tokens)
            count = int("".join(count_text).strip()) if count_text is not None else 0
            default = _optional(tokens) if count else None
            _skip_spaces(tokens)
            if (
                not _CONTROL_WORD.fullmatch(name)
                or not 0 <= count <= 9
                or not tokens
                or tokens[0] != "{"
            ):
                return tex
            body = _argument(tokens)
            if any(
                token in {"#", r"\newcommand"} or (token.startswith("#") and int(token[1:]) > count)
                for token in body
            ):
                return tex
            macros[name] = _Macro(count, default, body)
            _skip_spaces(tokens)
        if not macros or any(token == r"\newcommand" for token in tokens):
            return tex
        return _expand(tokens, macros)
    except UnsupportedLatexError:
        raise
    except (IndexError, ValueError):
        return tex


def _skip_spaces(tokens: deque[str]) -> None:
    while tokens and tokens[0].isspace():
        tokens.popleft()


def _argument(tokens: deque[str]) -> list[str]:
    _skip_spaces(tokens)
    first = tokens.popleft()
    if first == "}":
        raise ValueError("Missing TeX argument")
    return _group(tokens, "}") if first == "{" else [first]


def _optional(tokens: deque[str]) -> list[str] | None:
    _skip_spaces(tokens)
    if not tokens or tokens[0] != "[":
        return None
    tokens.popleft()
    return _group(tokens, "]")


def _group(tokens: deque[str], closing: str) -> list[str]:
    depth = 0
    group = []
    while tokens:
        token = tokens.popleft()
        if token == closing and not depth:
            return group
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        group.append(token)
    raise ValueError("Unclosed TeX argument")


def _expand(tokens: deque[str], macros: dict[str, _Macro]) -> str:
    expanded: list[str] = []
    remaining = _MAX_EXPANSION_CHARS - sum(map(len, tokens))
    expansions = 0
    while tokens:
        token = tokens.popleft()
        macro = macros.get(token)
        if macro is None:
            if (
                expanded
                and _CONTROL_WORD.fullmatch(expanded[-1])
                and token[0].isascii()
                and token[0].isalpha()
            ):
                expanded.append(" ")
            expanded.append(token)
            continue
        expansions += 1
        if expansions > _MAX_EXPANSIONS:
            raise UnsupportedLatexError("equation-local macro expansion exceeded its step limit")
        _skip_spaces(tokens)
        arguments = []
        if macro.default is not None:
            value = _optional(tokens)
            arguments.append(macro.default if value is None else value)
        arguments.extend(_argument(tokens) for _ in range(macro.count - len(arguments)))
        for part in reversed(macro.body):
            replacement = arguments[int(part[1:]) - 1] if part.startswith("#") else (part,)
            remaining -= sum(map(len, replacement))
            if remaining < 0:
                raise UnsupportedLatexError(
                    "equation-local macro expansion exceeded its length limit"
                )
            tokens.extendleft(reversed(replacement))
    return "".join(expanded)
