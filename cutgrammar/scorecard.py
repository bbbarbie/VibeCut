"""A scorecard for a finished edit, and how close it comes to a person's.

The Oct 16 evaluation's point: the 40/30/20/10 split says what matters but
measures nothing. This is the first measurable piece of a benchmark, and it
works on finished videos only, so any two edits of one shoot can be put
side by side -- VibeCut's and the creator's own, or two versions of VibeCut:

- pace: shots, median and longest shot, share of shots over 4 s
- loudness: integrated LUFS (social video sits near -14)
- agreement (with a reference edit): which of the person's moments the
  edit also shows, matched picture to picture -- the evaluation's
  "agreement with human editors on clips worth keeping"

Face time needs a face detector, which runs only on a Mac (Vision); here it
is reported as not checked rather than guessed (evidence.py's rule).

Matching is done on the 48x27 frames `media.load` already decodes: each
shot's frames, grey, centred and scaled (so a colour grade or a brightness
change doesn't hide a match), compared by correlation, best pair of
frames wins. Burned-in captions differ between edits; they are small at
this size. MATCH is a prior, set on one pair of real edits.

    python -m cutgrammar.scorecard vibecut.mp4 --reference mine.mov
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field

import numpy as np

from . import media, shots as shotdet

LONG_S = 4.0       # a shot past this reads as long on a short vertical vlog [prior]
MATCH = 0.80       # correlation at which two shots show the same moment [prior]
SAMPLES = 6        # frames per shot compared


@dataclass
class Card:
    path: str
    duration: float
    shots: int
    median_shot_s: float
    longest_shot_s: float
    long_share: float
    lufs: float | None
    face_share: str = "not checked (needs the Mac's face detector)"
    agreement: dict = field(default_factory=dict)


def _grey(frames: np.ndarray) -> np.ndarray:
    g = frames.astype(np.float32).mean(axis=-1).reshape(len(frames), -1)
    g -= g.mean(axis=1, keepdims=True)
    g /= np.linalg.norm(g, axis=1, keepdims=True) + 1e-6
    return g


def fingerprints(m: media.Media, cuts: list) -> list[np.ndarray]:
    """Per shot: SAMPLES normalised grey frames from its middle 80%."""
    out = []
    for s in cuts:
        a, b = s.start_frame, s.end_frame
        pad = int((b - a) * 0.1)
        idx = np.linspace(a + pad, max(a + pad, b - 1 - pad), SAMPLES).astype(int)
        out.append(_grey(m.frames[np.clip(idx, 0, len(m.frames) - 1)]))
    return out


def similarity(x: np.ndarray, y: np.ndarray) -> float:
    return float((x @ y.T).max())


def card(path: str) -> tuple[Card, media.Media, list]:
    m = media.load(path)
    cuts = shotdet.detect(m)
    lens = np.array([s.duration for s in cuts]) if cuts else np.zeros(1)
    c = Card(path=path, duration=round(m.duration, 2), shots=len(cuts),
             median_shot_s=round(float(np.median(lens)), 2), longest_shot_s=round(float(lens.max()), 2),
             long_share=round(float((lens > LONG_S).mean()), 2), lufs=media.loudness_lufs(path))
    return c, m, cuts


def agreement(edit: tuple, ref: tuple) -> dict:
    """Which of the reference edit's shots the edit also shows."""
    (_, em, ecuts), (_, rm, rcuts) = edit, ref
    ef, rf = fingerprints(em, ecuts), fingerprints(rm, rcuts)
    found, rows = 0, []
    for i, (s, f) in enumerate(zip(rcuts, rf)):
        best = max(((similarity(f, g), j) for j, g in enumerate(ef)), default=(0.0, -1))
        hit = best[0] >= MATCH
        found += hit
        rows.append({"ref_shot": i + 1, "at": round(s.start_t, 1), "len": round(s.duration, 1),
                     "in_edit": hit, "edit_shot": best[1] + 1 if hit else None, "score": round(best[0], 2)})
    return {"reference": ref[0].path, "ref_shots": len(rcuts), "shown": found,
            "share": round(found / max(1, len(rcuts)), 2), "shots": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edit")
    ap.add_argument("--reference", help="a person's own edit of the same shoot")
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args(argv)
    edit = card(args.edit)
    cards = [edit[0]]
    if args.reference:
        ref = card(args.reference)
        edit[0].agreement = agreement(edit, ref)
        cards.append(ref[0])
    for c in cards:
        loud = f"{c.lufs:.1f} LUFS" if c.lufs is not None else "no sound"
        print(f"{c.path}\n  {c.duration:.0f} s · {c.shots} shots · median {c.median_shot_s:.1f} s · "
              f"longest {c.longest_shot_s:.1f} s · {c.long_share:.0%} over {LONG_S:g} s · {loud}\n"
              f"  face time: {c.face_share}")
    if edit[0].agreement:
        a = edit[0].agreement
        print(f"agreement: shows {a['shown']} of the {a['ref_shots']} moments in the reference ({a['share']:.0%})")
    if args.json:
        with open(args.json, "w") as f:
            json.dump([asdict(c) for c in cards], f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
