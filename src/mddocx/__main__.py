"""Support ``python -m mddocx`` as an alias for the console entry point."""

from __future__ import annotations

from mddocx.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
