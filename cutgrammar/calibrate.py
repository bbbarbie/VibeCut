"""Calibration: thresholds derived from videos, not guessed.

The rule that matters most (CLAUDE.md): every threshold in grammar.py is a
guess until it has been checked against a distribution -- edits known to
be well cut on one side, edits known not to be on the other. This module
measures both sets with the same analyser the app uses, lays the two
distributions side by side per finding, and proposes the cut point that
best separates them. It never changes a threshold: the numbers go into a
dated record under design/research/calibration/ and a person moves the
constant in grammar.py, citing it.

What "separates" means here: each finding has one raw value per video
(rhythm_cv, cut_on_motion, jl_cuts, continuity, ...). For a candidate cut
point c and a direction ("good is below c" or "good is above c") the
balanced accuracy is the mean of the two classes' hit rates; the proposal
is the c with the highest, searched at the midpoints between neighbouring
sorted values. The AUC (rank statistic, direction-free) says whether the
finding carries any signal at all: 0.5 is a coin toss. With fewer than
MIN_PER_SIDE videos a side, the record says "thin" and the proposal is
marked as such -- a threshold set on four videos is still a guess.

Labels are the caller's: "good" and "bad" mean whatever the person who
assembled the sets meant (references they chose vs. edits they rejected),
and the record names the sets so that meaning travels with the numbers.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import grammar, media
from . import shots as shots_mod

MIN_PER_SIDE = 8          # fewer than this a side: the record says "thin"
LIMIT_S = 90.0            # the first stretch of each video is enough for the per-cut measures
                          # and keeps a 7-minute 4K export from costing 2 minutes of decode

# The thresholds as they stand in grammar.py, so the record can show the
# guess next to the proposal. (lo, hi) = the OK band; outside it is WARN/BAD.
# `good_is` says which side a well-cut edit is expected on when one-sided.
CURRENT = {
    "rhythm_cv": {"ok": (0.35, 1.4), "good_is": "inside"},
    "cut_on_motion": {"ok": (0.55, None), "good_is": "above"},
    "jl_cuts": {"ok": (None, 0.45), "good_is": "below"},
    "continuity": {"ok": (None, 0.0), "good_is": "below"},
    "duplicates": {"ok": (None, 0.0), "good_is": "below"},
    "first_cut": {"ok": (None, 5.0), "good_is": "below"},
    "first_speech": {"ok": (None, 3.0), "good_is": "below"},
    "loudness": {"ok": (-16.0, -12.5), "good_is": "inside"},
    "long_shot": {"ok": (None, 12.0), "good_is": "below"},
}


@dataclass
class Measured:
    path: str
    label: str                      # "good" | "bad"
    name: str
    duration: float
    n_shots: int
    values: dict[str, float]
    error: str | None = None


@dataclass
class Proposal:
    key: str
    good: list[float]
    bad: list[float]
    auc: float                      # P(good value > bad value), ties half
    cut: float | None               # proposed threshold
    good_is: str                    # "above" | "below" the cut
    balanced_acc: float
    current: dict | None
    thin: bool
    note: str = ""
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# measuring
# --------------------------------------------------------------------------

def head(path: str, cache: Path, limit_s: float = LIMIT_S) -> str:
    """The first `limit_s` seconds of a video, stream-copied into the cache
    (one decode of 90 s instead of 7 min). Returns the path to load."""
    cache.mkdir(parents=True, exist_ok=True)
    st = os.stat(path)
    out = cache / f"{abs(hash((path, st.st_size, int(st.st_mtime))))}-{int(limit_s)}s.mp4"
    if not out.exists():
        p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-t", str(limit_s), "-c", "copy",
                            "-movflags", "+faststart", str(out)], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stderr[-300:])
    return str(out)


def measure(path: str, label: str, cache: Path | None = None, limit_s: float | None = LIMIT_S) -> Measured:
    name = Path(path).name
    try:
        src = head(path, cache or Path(".vibecut-calib"), limit_s) if limit_s else path
        m = media.load(src)
        sh = shots_mod.detect(m)
        r = grammar.analyze(m, sh)
        vals = {f.key: float(f.value) for f in r.findings if f.value is not None}
        return Measured(path, label, name, m.duration, r.n_shots, vals)
    except Exception as e:  # noqa: BLE001 -- one unreadable file must not sink the set
        return Measured(path, label, name, 0.0, 0, {}, error=str(e)[:200])


# --------------------------------------------------------------------------
# the numbers
# --------------------------------------------------------------------------

def auc(good: list[float], bad: list[float]) -> float:
    """P(a good value ranks above a bad one), ties counting half."""
    if not good or not bad:
        return 0.5
    g, b = np.asarray(good)[:, None], np.asarray(bad)[None, :]
    return float(((g > b).mean() + 0.5 * (g == b).mean()))


def best_cut(good: list[float], bad: list[float]) -> tuple[float | None, str, float]:
    """The cut point and direction with the highest balanced accuracy."""
    if not good or not bad:
        return None, "below", 0.5
    vals = np.unique(np.concatenate([good, bad]))
    if len(vals) < 2:
        return None, "below", 0.5
    cands = (vals[:-1] + vals[1:]) / 2
    g, b = np.asarray(good), np.asarray(bad)
    best = (0.5, None, "below")
    for c in cands:
        above = 0.5 * ((g > c).mean() + (b <= c).mean())
        below = 0.5 * ((g < c).mean() + (b >= c).mean())
        for acc, side in ((above, "above"), (below, "below")):
            if acc > best[0] + 1e-9:
                best = (acc, float(c), side)
    return best[1], best[2], best[0]


def propose(rows: list[Measured]) -> list[Proposal]:
    keys = sorted({k for r in rows for k in r.values})
    out = []
    for k in keys:
        good = [r.values[k] for r in rows if r.label == "good" and k in r.values]
        bad = [r.values[k] for r in rows if r.label == "bad" and k in r.values]
        a = auc(good, bad)
        cut, side, acc = best_cut(good, bad)
        thin = min(len(good), len(bad)) < MIN_PER_SIDE
        if not good or not bad:
            note = "one side is empty: nothing to compare"
        elif abs(a - 0.5) < 0.1:
            note = "no signal: this finding doesn't tell the two sets apart"
        elif thin:
            note = "thin: fewer than %d a side, so this proposal is still a guess" % MIN_PER_SIDE
        else:
            note = "separates" if acc >= 0.75 else "weak"
        out.append(Proposal(k, good, bad, round(a, 3), None if cut is None else round(cut, 4), side,
                            round(acc, 3), CURRENT.get(k), thin, note,
                            {"good_median": float(np.median(good)) if good else None,
                             "bad_median": float(np.median(bad)) if bad else None,
                             "good_p10_p90": [float(np.percentile(good, 10)), float(np.percentile(good, 90))] if good else None,
                             "bad_p10_p90": [float(np.percentile(bad, 10)), float(np.percentile(bad, 90))] if bad else None}))
    return out


# --------------------------------------------------------------------------
# the record
# --------------------------------------------------------------------------

def record(rows: list[Measured], props: list[Proposal], sets: dict[str, str], out_dir: Path,
           stamp: str | None = None) -> tuple[Path, Path]:
    """A dated JSON (the numbers) and a Markdown page (the reading) side by side."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or time.strftime("%Y-%m-%d")
    data = {"date": stamp, "sets": sets, "limit_s": LIMIT_S, "min_per_side": MIN_PER_SIDE,
            "videos": [r.__dict__ for r in rows], "proposals": [p.__dict__ for p in props]}
    jp = out_dir / f"{stamp}.json"
    jp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    ng = sum(r.label == "good" and not r.error for r in rows)
    nb = sum(r.label == "bad" and not r.error for r in rows)
    lines = [f"# Calibration · {stamp}", "",
             f"**Good** ({ng}): {sets.get('good', '')}  ", f"**Bad** ({nb}): {sets.get('bad', '')}", "",
             f"Each video's first {LIMIT_S:.0f} s, through `grammar.analyze`. A proposal is the cut point "
             f"with the best balanced accuracy; AUC 0.5 is a coin toss. Fewer than {MIN_PER_SIDE} a side is *thin*. "
             "Nothing here changes a threshold by itself.", "",
             "| finding | good median | bad median | AUC | proposal | current OK band | reading |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for p in props:
        cur = p.current["ok"] if p.current else None
        band = ("–" if cur is None else
                f"{'' if cur[0] is None else cur[0]} … {'' if cur[1] is None else cur[1]}")
        prop = "–" if p.cut is None else f"good {p.good_is} {p.cut:.3g} (acc {p.balanced_acc:.2f})"
        gm, bm = p.extra["good_median"], p.extra["bad_median"]
        lines.append(f"| {p.key} | {'' if gm is None else f'{gm:.3g}'} | {'' if bm is None else f'{bm:.3g}'} | "
                     f"{p.auc:.2f} | {prop} | {band} | {p.note} |")
    errs = [r for r in rows if r.error]
    if errs:
        lines += ["", "Skipped:", *[f"- {r.name}: {r.error}" for r in errs]]
    lines += ["", "## Videos", "", "| set | video | length | shots |", "| --- | --- | --- | --- |",
              *[f"| {r.label} | {r.name} | {r.duration:.0f} s | {r.n_shots} |" for r in rows if not r.error]]
    mp = out_dir / f"{stamp}.md"
    mp.write_text("\n".join(lines) + "\n")
    return jp, mp
