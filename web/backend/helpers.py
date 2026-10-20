"""Apple helpers that came built with the Mac app.

On a developer's Mac each helper compiles itself with swiftc on first use.
Someone who downloaded VibeCut.app has no swiftc, so the app ships them
already built and its launcher points VIBECUT_HELPERS at that folder.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def prebuilt(name: str) -> Path | None:
    d = os.environ.get("VIBECUT_HELPERS")
    if not d or sys.platform != "darwin":
        return None
    p = Path(d) / name
    return p if p.is_file() and os.access(p, os.X_OK) else None


def can_build() -> bool:
    return sys.platform == "darwin" and shutil.which("swiftc") is not None
