#!/usr/bin/env python3
"""Calibrate the grammar's thresholds against videos you've judged.

    python calibrate.py --good refs/*.mp4 --bad exports/*.mp4
    python calibrate.py --good-dir ~/good --bad-dir ~/bad --note "my picks vs my rejects"
    python calibrate.py --good-links links.txt ...     # one link a line, fetched with yt-dlp

Measures the first 90 s of each with the same analyser the app uses, lays
the two distributions side by side per finding, proposes a cut point, and
writes design/research/calibration/<date>.{json,md}. Changes nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from cutgrammar import calibrate as cal

CACHE = Path(os.environ.get("VIBECUT_CACHE", os.path.expanduser("~/.cache/vibecut"))) / "calibration"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


def _files(paths: list[str], d: str | None) -> list[str]:
    out = [os.path.expanduser(p) for p in paths]
    if d:
        out += sorted(str(p) for p in Path(os.path.expanduser(d)).iterdir() if p.suffix.lower() in VIDEO_EXT)
    return [p for p in out if os.path.isfile(p)]


def _ytdlp() -> list[str]:
    """The venv's yt_dlp when it has one (kept current: YouTube answers an old
    yt-dlp with 403s), else whatever yt-dlp is on the path."""
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        return ["yt-dlp", "--no-update"]


def _fetch(links_file: str, label: str) -> list[str]:
    """Links to files at ≤480p, whole (a sectioned download goes through
    ffmpeg straight to the CDN and gets a 403 on this yt-dlp); the harness
    cuts the first 90 s locally. Cached by link."""
    d = CACHE / "links" / label
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for line in Path(links_file).read_text().splitlines():
        url = line.strip()
        if not url or url.startswith("#"):
            continue
        target = d / (hashlib.sha1(url.encode()).hexdigest()[:12] + ".mp4")   # stable across runs
        if not target.exists():
            print(f"  fetching {url}")
            p = subprocess.run([*_ytdlp(), "--no-playlist", "--quiet", "--no-warnings", "--no-part",
                                "-f", "b[height<=480][ext=mp4]/b[height<=480]/bv*[height<=480]+ba/b",
                                "--merge-output-format", "mp4", "--write-info-json",
                                "-o", str(target), "--", url],
                               capture_output=True, text=True)
            if p.returncode != 0 or not target.exists():
                print(f"  skipped {url}: {p.stderr.strip()[-160:]}", file=sys.stderr)
                continue
        out.append(str(target))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--good", nargs="*", default=[], help="well-cut videos")
    ap.add_argument("--bad", nargs="*", default=[], help="videos that aren't")
    ap.add_argument("--good-dir")
    ap.add_argument("--bad-dir")
    ap.add_argument("--good-list", help="a file of paths, one a line (spaces in names are fine)")
    ap.add_argument("--bad-list")
    ap.add_argument("--good-links", help="a file of links, one a line (needs yt-dlp)")
    ap.add_argument("--bad-links")
    ap.add_argument("--note", default="", help="what the two sets are, in your words")
    ap.add_argument("--out", default="design/research/calibration")
    ap.add_argument("--stamp", help="record name (default: today)")
    args = ap.parse_args()

    def listed(f: str | None) -> list[str]:
        return [l.strip() for l in Path(f).read_text().splitlines() if l.strip()] if f else []
    good = _files(args.good + listed(args.good_list), args.good_dir) + (_fetch(args.good_links, "good") if args.good_links else [])
    bad = _files(args.bad + listed(args.bad_list), args.bad_dir) + (_fetch(args.bad_links, "bad") if args.bad_links else [])
    if not good or not bad:
        print("need at least one video on each side", file=sys.stderr)
        return 2
    rows = []
    for label, paths in (("good", good), ("bad", bad)):
        for p in paths:
            print(f"  {label:4} {Path(p).name[:60]}", end=" ", flush=True)
            r = cal.measure(p, label, CACHE / "heads")
            print(f"— {r.error}" if r.error else f"— {r.n_shots} shots, {len(r.values)} findings")
            rows.append(r)
    props = cal.propose(rows)
    sets = {"good": f"{len(good)} videos" + (f" — {args.note}" if args.note else ""), "bad": f"{len(bad)} videos"}
    jp, mp = cal.record(rows, props, sets, Path(args.out), args.stamp)
    print(f"\n  wrote {mp}\n  wrote {jp}\n")
    for p in props:
        prop = "–" if p.cut is None else f"good {p.good_is} {p.cut:.3g}"
        print(f"  {p.key:14} AUC {p.auc:.2f}  {prop:24} {p.note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
