"""A read-only, hash-backed inventory of a shoot, and a check against it.

Adapted from montage-vlog-compiler's media_inventory.py / verify_inventory.py
(MIT; see NOTICE). The editing reason for it: an edit is a list of in/out
points into files. If a file is re-exported, trimmed in Photos, or swapped
for another take with the same name, every point into it silently lands
somewhere else. The index cache keys on path + size + mtime, which catches
most of that; a content hash catches all of it, and says *which* files
changed rather than just re-indexing them.

Nothing here writes into the footage folder. Metadata only (ffprobe): what
a clip's duration, orientation and tracks are -- never what is in it.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

from . import evidence
from .media import _parse_fps, _rotation, probe

SCHEMA = "vibecut-inventory/1"
VIDEO_EXT = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find(root: Path) -> dict[str, Path]:
    """Relative path -> file, for every video under `root` (hidden files skipped)."""
    return {p.relative_to(root).as_posix(): p
            for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix.lower() in VIDEO_EXT
            and not any(part.startswith(".") for part in p.relative_to(root).parts)}


def describe(path: Path) -> dict:
    info = probe(str(path))
    video = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    audio = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not video:
        raise ValueError("no video stream")
    v = video[0]
    rot = _rotation(v)
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    dur = info.get("format", {}).get("duration") or v.get("duration")
    return {
        "duration": round(float(dur), 3) if dur not in (None, "N/A") else None,
        "codec": v.get("codec_name"),
        "fps": round(_parse_fps(v), 3),
        "coded_size": [w, h],
        # what the viewer sees: a portrait iPhone clip is stored landscape
        "display_size": [h, w] if rot in (90, 270) else [w, h],
        "rotation": rot,
        "audio_tracks": len(audio),
    }


def build(root: str | Path) -> dict:
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"not a folder: {root}")
    files, failed, total = [], 0, 0.0
    for rel, p in find(root).items():
        st = p.stat()
        rec = {"path": rel, "real_path": str(p.resolve()), "size": st.st_size,
               "sha256": sha256(p), "status": "ok", "error": None}
        try:
            rec.update(describe(p))
            total += rec.get("duration") or 0.0
        except (OSError, RuntimeError, ValueError) as e:
            rec.update(status="probe_failed", error=str(e)[:300])
            failed += 1
        files.append(rec)
    return {
        "schema": SCHEMA,
        "made_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "root": str(root),
        "evidence": [evidence.META],   # nothing about what's in frame, or how it sounds
        "summary": {"files": len(files), "probe_failed": failed,
                    "bytes": sum(f["size"] for f in files), "duration": round(total, 3)},
        "files": files,
    }


def verify(manifest: dict, root: str | Path | None = None) -> dict:
    """Is the folder still what the inventory says? Missing, changed, and
    files that were never in it are reported by name, never fixed."""
    if manifest.get("schema") != SCHEMA or not isinstance(manifest.get("files"), list):
        raise ValueError("not a VibeCut inventory")
    root = Path(root or manifest["root"]).expanduser().resolve()
    if not root.is_dir():
        # An unmounted card or drive looks exactly like "everything missing".
        raise ValueError(f"folder not found (is the drive mounted?): {root}")
    expected = {f["path"]: f for f in manifest["files"]}
    actual = find(root)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = []
    for rel in sorted(set(expected) & set(actual)):
        p, want = actual[rel], expected[rel]
        size = p.stat().st_size
        digest = sha256(p) if size == want["size"] else None
        if size != want["size"] or digest != want["sha256"]:
            changed.append({"path": rel, "size": [want["size"], size],
                            "sha256": [want["sha256"], digest or sha256(p)]})
    ok = not (missing or changed or extra)
    return {"schema": SCHEMA, "root": str(root), "status": "pass" if ok else "fail",
            "summary": {"expected": len(expected), "found": len(actual), "missing": len(missing),
                        "changed": len(changed), "unexpected": len(extra)},
            "missing": missing, "changed": changed, "unexpected": extra}
