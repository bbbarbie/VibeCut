"""The inventory notices exactly what changed, and changes nothing itself.

A folder is recorded, then altered in one way at a time -- a file
re-exported with the same name and size, one deleted, one added -- and
verify has to name that file and only that file. A check that passed an
untouched folder but missed a same-size swap would be no check at all.

    python tests/test_inventory.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import inventory  # noqa: E402


def _ff(args: list[str]) -> None:
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[:400])


def clip(path: Path, src: str, rotate: int | None = None, audio: bool = True) -> None:
    args = ["-f", "lavfi", "-i", f"{src}=size=320x180:rate=30"]
    if audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1"]
    args += ["-t", "1", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    if audio:
        args += ["-c:a", "aac"]
    if rotate is None:
        _ff([*args, str(path)])
        return
    # Phones store portrait video landscape and flag it; do the same.
    flat = path.with_suffix(".flat" + path.suffix)
    _ff([*args, str(flat)])
    _ff(["-display_rotation", str(rotate), "-i", str(flat), "-c", "copy", str(path)])
    flat.unlink()


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in root.rglob("*")}


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "shoot"
        (root / "day2").mkdir(parents=True)
        clip(root / "IMG_0001.MOV", "testsrc")
        clip(root / "day2" / "IMG_0002.mp4", "smptebars", audio=False)
        clip(root / "portrait.mp4", "testsrc2", rotate=90)
        (root / "notes.txt").write_text("not a video")
        (root / ".hidden.mp4").write_bytes(b"sidecar")

        before = snapshot(root)
        inv = inventory.build(root)
        check("building reads, never writes", snapshot(root) == before)
        files = {f["path"]: f for f in inv["files"]}
        check("finds videos in subfolders, skips others and hidden files",
              sorted(files) == ["IMG_0001.MOV", "day2/IMG_0002.mp4", "portrait.mp4"], str(sorted(files)))
        check("audio tracks counted", files["IMG_0001.MOV"]["audio_tracks"] == 1
              and files["day2/IMG_0002.mp4"]["audio_tracks"] == 0)
        p = files["portrait.mp4"]
        check("rotation gives the size the viewer sees", p["display_size"] == [180, 320]
              and p["coded_size"] == [320, 180], f"{p['coded_size']} -> {p['display_size']} @ {p['rotation']}")
        check("claims metadata only", inv["evidence"] == ["meta"])

        check("an untouched folder passes", inventory.verify(inv)["status"] == "pass")

        # Same name, same size, different bytes: a re-export.
        target = root / "IMG_0001.MOV"
        raw = bytearray(target.read_bytes())
        raw[len(raw) // 2] ^= 0xFF
        target.write_bytes(bytes(raw))
        r = inventory.verify(inv)
        check("a same-size swap is caught, by name",
              r["status"] == "fail" and [c["path"] for c in r["changed"]] == ["IMG_0001.MOV"]
              and not r["missing"] and not r["unexpected"], str(r["summary"]))

        (root / "day2" / "IMG_0002.mp4").unlink()
        clip(root / "IMG_0003.mp4", "testsrc")
        r = inventory.verify(inv)
        check("missing and new files are named",
              r["missing"] == ["day2/IMG_0002.mp4"] and r["unexpected"] == ["IMG_0003.mp4"], str(r["summary"]))

        # Moved to another drive: check the copy without editing the record.
        moved = Path(d) / "card"
        shutil.copytree(root, moved)
        r = inventory.verify(inv, moved)
        check("verify can check a copy elsewhere", r["root"] == str(moved.resolve()) and r["summary"]["found"] == 3)

        try:
            inventory.verify(inv, Path(d) / "unmounted")
            check("an absent folder is an error, not 'all missing'", False)
        except ValueError as e:
            check("an absent folder is an error, not 'all missing'", "mounted" in str(e), str(e))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
