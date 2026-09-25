"""A finding may only claim what its reading could see.

The same file is read twice: every frame (`media.load`) and keyframes only
(`media.load_index`). The two differ in exactly one respect -- whether the
picture between samples was seen -- so the gate has to move with it:
motion-dependent findings get a verdict from the full read and are marked
"not checked" from the keyframe read, while findings visible in stills keep
their verdict both ways. A gate that fired on everything, or on nothing,
would pass neither half.

    python tests/test_evidence.py
"""

from __future__ import annotations

import copy
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import evidence, grammar, media, reject, shots  # noqa: E402
from cutgrammar.signals import ClipSignals  # noqa: E402

CLIPS = [
    ("testsrc2=size=320x180:rate=30", 3.0, 300),
    ("color=c=crimson:size=320x180:rate=30", 2.0, 500),
    ("smptebars=size=320x180:rate=30", 2.5, 700),
    ("color=c=darkblue:size=320x180:rate=30", 4.0, 200),
    ("testsrc=size=320x180:rate=30", 2.0, 900),
]


def _ff(args: list[str]) -> None:
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[:400])


def build(d: str) -> str:
    parts = []
    for i, (src, dur, freq) in enumerate(CLIPS):
        out = os.path.join(d, f"c{i}.mp4")
        _ff(["-f", "lavfi", "-i", src, "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}",
             "-t", str(dur), "-c:v", "libx264", "-preset", "ultrafast", "-g", "30",
             "-c:a", "aac", "-pix_fmt", "yuv420p", out])
        parts.append(out)
    lst = os.path.join(d, "list.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p in parts)
    out = os.path.join(d, "edit.mp4")
    _ff(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
    return out


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as d:
        path = build(d)
        full = media.load(path)
        idx = media.load_index(path)

        check("a full decode carries motion", evidence.MOTION in evidence.available(full),
              str(sorted(evidence.available(full))))
        check("a keyframe index does not", evidence.MOTION not in evidence.available(idx),
              str(sorted(evidence.available(idx))))
        check("both carry stills and sound",
              {evidence.STILL, evidence.AUDIO} <= evidence.available(idx) & evidence.available(full))

        rf = {f.key: f for f in grammar.analyze(full, shots.detect(full)).findings}
        ri = {f.key: f for f in grammar.analyze(idx, shots.detect(idx)).findings}

        for key in ("cut_on_motion", "jl_cuts"):
            if key in rf:
                check(f"{key}: judged from the full decode", rf[key].verdict != grammar.PENDING, rf[key].verdict)
            if key in ri:
                check(f"{key}: not checked from keyframes", ri[key].verdict == grammar.PENDING
                      and ri[key].extra.get("lacking") == [evidence.MOTION], ri[key].verdict)
        # The keyframe read may be too sparse to produce a cut-on-motion number
        # at all; the same number, had it been measured that way, is withheld.
        f = copy.deepcopy(rf["cut_on_motion"])
        f.evidence = []
        grammar.gate([f], evidence.available(idx))
        check("cut_on_motion: withheld when only keyframes were read",
              f.verdict == grammar.PENDING and f.value == rf["cut_on_motion"].value, f.verdict)
        for key in ("rhythm_cv", "continuity"):
            if key in ri:
                check(f"{key}: stills are enough, verdict kept", ri[key].verdict != grammar.PENDING, ri[key].verdict)
        check("every finding names what it rests on",
              all(f.evidence for f in [*rf.values(), *ri.values()]))
        pend = [f for f in ri.values() if f.verdict == grammar.PENDING]
        check("a withheld verdict keeps its number", all("withheld_verdict" in f.extra for f in pend))

    # The rough cut reads the index, so a shake reason is a guess from stills
    # and says so; a lens-cap reason is visible in any still and doesn't.
    def sig(motion: float, luma: float) -> ClipSignals:
        n = 10
        return ClipSignals(duration=float(n), quality=[0.6] * n, sharpness=[0.8] * n, luma=[luma] * n,
                           contrast=[0.5] * n, motion=[motion] * n, subject=[0.8] * n, edge=[0.0] * n,
                           speech=[0.0] * n, voiced=[], thumb=[0.5] * 144)

    shaky = reject.judge(sig(40.0, 120.0))
    cap = reject.judge(sig(0.5, 3.0))
    check("shaking is rejected", shaky.rejected and shaky.code == "shaky", shaky.code)
    check("…and flagged as unseen motion", shaky.unverified() == [evidence.MOTION], str(shaky.unverified()))
    check("lens cap is rejected with nothing unseen", cap.rejected and cap.unverified() == [],
          f"{cap.code} {cap.unverified()}")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
