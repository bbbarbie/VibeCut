"""The trim offers its top windows; a picture judge may choose between them.

Pins down what has to hold whatever the judge says:
- the rules' first choice is unchanged (best_window == candidates[0]);
- the runners-up are different moments, and a clip with one good stretch
  offers only that one -- there is nothing to choose between;
- with no key, or a judge that fails, the rules' pick stands and the shot
  says so; a failed shot isn't asked again on every click;
- a judge's answer is used, said in the reason, and cached on disk, so the
  next compute (every click at the gate) doesn't ask again.

Run: python tests/test_moments.py
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-moments-")
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import trim  # noqa: E402
from cutgrammar.signals import ClipSignals  # noqa: E402
from web.backend import cut, indexer, llm, moments  # noqa: E402

N = 30


def _sig(good: list[range]) -> ClipSignals:
    q = [0.3] * N
    for r in good:
        for i in r:
            q[i] = 0.95
    return ClipSignals(duration=float(N), quality=q, sharpness=[0.8] * N, luma=[120.0] * N,
                       contrast=[0.8] * N, motion=[2.0] * N, subject=[0.8] * N, edge=[0.0] * N,
                       speech=[0.0] * N, voiced=[], thumb=[0.0] * 144)


def _clips(cid: str, good: list[range], samples: bool = True) -> dict[str, dict]:
    rec = {"id": cid, "name": "a.mov", "duration": float(N), "capture_time": None,
           "signals": _sig(good).to_json(),
           "shots": [{"index": 0, "start": 0.0, "end": float(N), "quality": 0.8}]}
    if samples:
        d = indexer.clip_dir(cid) / "samples"
        d.mkdir(parents=True, exist_ok=True)
        files = []
        for i in range(N):
            (d / f"{i:04d}.jpg").write_bytes(b"\xff\xd8 frame %d" % i)
            files.append(f"samples/{i:04d}.jpg")
        rec["samples"] = {"times": [float(i) for i in range(N)], "files": files}
    return {cid: rec}


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    # -- candidates -------------------------------------------------------
    two = _sig([range(4, 10), range(19, 25)])
    cs = trim.candidates(two, 5)
    best = trim.best_window(two, 5)
    check("the rules' first choice is unchanged", (cs[0].start, cs[0].end) == (best.start, best.end),
          f"{cs[0].start}–{cs[0].end} vs {best.start}–{best.end}")
    check("two good stretches are both offered", len(cs) >= 2 and {int(cs[0].start) // 10, int(cs[1].start) // 10} >= {0, 1}
          or any(abs(c.start - 19) <= 1 for c in cs[1:]), str([(c.start, c.end) for c in cs]))
    overlap = max((min(a.end, b.end) - max(a.start, b.start)) / (a.end - a.start)
                  for i, a in enumerate(cs) for b in cs[i + 1:]) if len(cs) > 1 else 0
    check("no two options are mostly the same seconds", overlap <= 1 / 3, f"{overlap:.2f}")

    # one good stretch in an otherwise poor clip: nothing worth choosing between
    lone = trim.candidates(_sig([range(10, 16)]), 5)
    check("one good stretch offers only itself", len(lone) == 1, str([(c.start, c.end) for c in lone]))

    # -- no key -> the rules -----------------------------------------------
    check("no key here", not llm.available())
    clips = _clips("clip0000000a", [range(4, 10), range(19, 25)])
    sid = "clip0000000a:0"
    plan = cut.compute(clips)
    s = plan.clips["clip0000000a"]["shots"][sid]
    check("without a key the rules' pick stands", s["window"] == s["options"][0] and s["picked_by"] == "rules",
          f"{s['window']} by {s['picked_by']}")
    check("and the shot still offers its options", len(s["options"]) >= 2, str(s["options"]))

    # -- a judge that answers ------------------------------------------------
    calls = []

    def judge(opts: list[dict]) -> tuple[int, str]:
        calls.append(opts)
        return 1, "she laughs here"

    plan = cut.compute(clips, ask=judge)
    s = plan.clips["clip0000000a"]["shots"][sid]
    check("the judge sees every option with frames", len(calls) == 1 and len(calls[0]) == len(s["options"])
          and all(1 <= len(o["frames"]) <= moments.FRAMES for o in calls[0]), str(len(calls)))
    check("its pick is the window", s["window"] == s["options"][1] and s["picked_by"] == "claude", str(s["window"]))
    check("and the reason says who chose and why", "she laughs here" in s["reason_en"]
          and "rules alone" in s["reason_en"], s["reason_en"])
    check("the gate's suggestion is the judged window", s["auto"] == s["options"][1], str(s["auto"]))

    plan = cut.override(plan, sid, "keep", clips)   # any click recomputes
    plan = cut.compute(clips, plan, ask=judge)
    check("answers are cached: a recompute doesn't ask again", len(calls) == 1, f"{len(calls)} calls")
    check("and the cached pick still holds", plan.clips["clip0000000a"]["shots"][sid]["picked_by"] == "claude")

    # -- a judge that fails ---------------------------------------------------
    clips_b = _clips("clip0000000b", [range(3, 9), range(20, 26)])
    sid_b = "clip0000000b:0"
    broken = []

    def fails(opts: list[dict]) -> tuple[int, str]:
        broken.append(1)
        raise llm.LLMError("no network")

    plan = cut.compute(clips_b, ask=fails)
    s = plan.clips["clip0000000b"]["shots"][sid_b]
    check("a failed answer leaves the rules' pick", s["window"] == s["options"][0] and s["picked_by"] == "rules",
          f"{s['window']} by {s['picked_by']}")
    cut.compute(clips_b, plan, ask=fails)
    check("and a failed shot isn't asked again on every click", len(broken) == 1, f"{len(broken)} calls")

    plan = cut.compute(_clips("clip0000000c", [range(3, 9), range(20, 26)]), ask=lambda o: (7, "out of range"))
    s = plan.clips["clip0000000c"]["shots"]["clip0000000c:0"]
    check("an answer that isn't one of the options is ignored", s["picked_by"] == "rules")

    plan = cut.compute(_clips("clip0000000d", [range(3, 9), range(20, 26)], samples=False), ask=judge)
    s = plan.clips["clip0000000d"]["shots"]["clip0000000d:0"]
    check("no frames on disk: nothing is sent, the rules' pick stands", s["picked_by"] == "rules" and len(calls) == 1)

    # -- frames ---------------------------------------------------------------
    rec = _clips("clip0000000e", [])["clip0000000e"]
    fs = moments.frames(rec, trim.Window(start=10.0, end=15.0, target=5, score=0, whole=False, reason_zh="", reason_en=""))
    check("start, middle and end frames, from inside the window", [f.name for f in fs] == ["0010.jpg", "0012.jpg", "0015.jpg"]
          or [f.name for f in fs] == ["0010.jpg", "0013.jpg", "0015.jpg"], str([f.name for f in fs]))

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_moments() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
