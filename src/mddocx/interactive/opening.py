from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def open_path(path: str | Path) -> None:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise OSError(f"Path does not exist: {target}")
    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]
        return
    command = ["open", str(target)] if sys.platform == "darwin" else ["xdg-open", str(target)]
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
