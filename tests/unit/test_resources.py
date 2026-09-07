from pathlib import Path
import pytest
from mddocx.resources import ResourceResolver
from mddocx.config import ResourcePolicy
from mddocx.diagnostics import MddocxError


def test_resource_traversal_blocked(tmp_path: Path):
    resolver = ResourceResolver(tmp_path, ResourcePolicy())
    with pytest.raises(MddocxError):
        resolver.resolve("../secret.png")
