"""Find dropped files on disk so nothing has to be copied.

A browser can't tell the page where a dropped file lives -- only its name,
size and modification time. On macOS Spotlight can: look the name up, keep
the candidate whose size and mtime match. A 30-clip 4K shoot is several GB;
finding it is ~0.1s, uploading it over localhost is most of the time budget.
Anything not found this way is uploaded instead (see app.upload).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor


def _mdfind(name: str) -> list[str]:
    q = 'kMDItemFSName == "%s"' % name.replace('"', '\\"')
    try:
        p = subprocess.run(["mdfind", q], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [l for l in p.stdout.splitlines() if l]


def _matches(path: str, size: int, mtime_ms: float | None) -> bool:
    try:
        st = os.stat(path)
    except OSError:
        return False
    if st.st_size != size:
        return False
    return mtime_ms is None or abs(st.st_mtime * 1000 - mtime_ms) < 2500


# Where people keep footage. Spotlight takes a while to see freshly copied
# files, so a dropped folder is also looked for by name under these.
ROOTS = ["~/Movies", "~/Desktop", "~/Downloads", "~/Pictures", "~/Documents", "~", "/Volumes"]
MAX_DEPTH = 3


def _folder_candidates(name: str) -> list[str]:
    out = []
    for root in ROOTS:
        root = os.path.expanduser(root)
        base = root.count(os.sep)
        for dirpath, dirs, _ in os.walk(root):
            if dirpath.count(os.sep) - base >= MAX_DEPTH:
                dirs[:] = []
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "Library"]
            if name in dirs:
                out.append(os.path.join(dirpath, name))
    return list(dict.fromkeys(out))


def _by_folder(files: list[dict]) -> dict[str, str]:
    tops = {f["relpath"].split("/")[0] for f in files if "/" in f["relpath"]}
    found: dict[str, str] = {}
    for top in tops:
        for cand in _folder_candidates(top):
            parent = os.path.dirname(cand)
            hits = {f["relpath"]: os.path.join(parent, f["relpath"]) for f in files
                    if f["relpath"].startswith(top + "/")
                    and _matches(os.path.join(parent, f["relpath"]), f["size"], f.get("mtime"))}
            if hits:
                found.update(hits)
                break
    return found


def _by_name(files: list[dict]) -> dict[str, str]:
    """Loose files (no folder in the drop): one walk of the usual roots."""
    want: dict[str, list[dict]] = {}
    for f in files:
        want.setdefault(f["name"], []).append(f)
    found: dict[str, str] = {}
    for root in ROOTS:
        root = os.path.expanduser(root)
        base = root.count(os.sep)
        for dirpath, dirs, names in os.walk(root):
            if dirpath.count(os.sep) - base >= MAX_DEPTH:
                dirs[:] = []
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "Library"]
            for n in names:
                for f in want.get(n, []):
                    p = os.path.join(dirpath, n)
                    if f["relpath"] not in found and _matches(p, f["size"], f.get("mtime")):
                        found[f["relpath"]] = p
            if len(found) == len(files):
                return found
    return found


def resolve(files: list[dict], known: list[str] | None = None) -> dict:
    """files: [{name, size, mtime, relpath}] -> {resolved: {relpath: path}, missing: [relpath]}"""
    # Already on the shelf? Then it's that file -- never copy it again.
    pre: dict[str, str] = {}
    for f in files:
        for k in known or []:
            if os.path.basename(k) == f["name"] and _matches(k, f["size"], None):
                pre[f["relpath"]] = k
                break
    files = [f for f in files if f["relpath"] not in pre]
    if sys.platform != "darwin" or not files:
        return {"resolved": pre, "missing": [f["relpath"] for f in files]}
    with ThreadPoolExecutor(max_workers=8) as ex:
        cands = list(ex.map(lambda f: [c for c in _mdfind(f["name"])
                                       if _matches(c, f["size"], f.get("mtime"))], files))
    # Where several copies match, prefer the folder most of the drop came from.
    home = Counter(os.path.dirname(c[0]) for c in cands if len(c) == 1)
    resolved, missing = {}, []
    for f, c in zip(files, cands):
        if not c:
            missing.append(f["relpath"])
            continue
        resolved[f["relpath"]] = max(c, key=lambda p: home[os.path.dirname(p)])
    for fallback in (_by_folder, _by_name):
        if missing:
            more = fallback([f for f in files if f["relpath"] in set(missing)])
            resolved.update(more)
            missing = [m for m in missing if m not in more]
    return {"resolved": {**pre, **resolved}, "missing": missing}
