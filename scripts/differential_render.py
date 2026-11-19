"""Compare the structural corpus against a checkout of an earlier release."""

from __future__ import annotations

import argparse
from difflib import unified_diff
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(src: Path) -> dict:
    env = dict(os.environ, PYTHONPATH=str(src))
    output = subprocess.check_output(
        [sys.executable, str(ROOT / "tests/test_structural_golden.py")], env=env, encoding="ascii"
    )
    return json.loads(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous_checkout", type=Path)
    args = parser.parse_args()
    previous = run(args.previous_checkout.resolve() / "src")
    candidate = run(ROOT / "src")
    diff = unified_diff(
        json.dumps(previous, indent=2, sort_keys=True).splitlines(),
        json.dumps(candidate, indent=2, sort_keys=True).splitlines(),
        fromfile=str(args.previous_checkout),
        tofile="candidate",
        lineterm="",
    )
    lines = list(diff)
    if lines:
        print("\n".join(lines))
    else:
        print("Structural corpus matches.")
    return int(bool(lines))


if __name__ == "__main__":
    raise SystemExit(main())
