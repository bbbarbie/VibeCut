"""Does the selector choose the way it claims to?

Every rule in select.py is checked by two cases that differ in one thing:
a rare label vs a common one, a face in the frame vs none, two takes of
one picture vs two pictures, a peak of action late in a clip vs early.
The rule has to move the choice; the number behind it is still a guess.

    python tests/test_select.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web.backend import select as sel  # noqa: E402
from web.backend import storyboard as sb  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
    if not cond:
        failures.append(name)


T0 = datetime(2026, 9, 22, 8, 30)


def shot(i: int, *, labels=None, face=0.0, faces=0, vec=None, when=None, quality=0.8, aesthetic=0.3,
         start=0.0, end=6.0, clip=None) -> sb.Shot:
    v = np.asarray(vec if vec is not None else np.eye(8)[i % 8], dtype=np.float32)
    v = v / (np.linalg.norm(v) + 1e-9)
    return sb.Shot(id=f"c{clip or i}:0", clip_id=f"c{clip or i}", clip_name=f"IMG_{i}.MOV", index=0,
                   start=start, end=end, thumb="", quality=quality, aesthetic=aesthetic, utility=False,
                   when=when if when is not None else T0 + timedelta(minutes=i), gps=None,
                   labels=labels or {"people": 0.9, "structure": 0.6}, faces=faces, face_area=face,
                   activity=0.5, vec=v, order=i)


def clips_for(shots: list[sb.Shot], **signals) -> dict[str, dict]:
    n = int(max(s.end for s in shots)) + 1

    def base() -> dict:   # one dict per clip, so a test can change one clip's signal
        b = {"subject": [0.3] * n, "motion": [10.0] * n, "contrast": [0.5] * n}
        b.update({k: list(v) for k, v in signals.items()})
        return b
    return {s.clip_id: {"duration": s.end, "signals": base()} for s in shots}


def scoring() -> None:
    print("scoring")
    common = [shot(i) for i in range(6)]
    rare = shot(9, labels={"plate": 0.9, "tableware": 0.8})
    pool = common + [rare]
    w = sel.idf(pool)
    clips = clips_for(pool)
    s_rare = sel.hero_score(rare, clips, w)[0]
    s_common = sel.hero_score(common[0], clips, w)[0]
    check("a rare label outranks the labels every clip shares", s_rare > s_common + 0.1,
          f"{s_rare:.2f} vs {s_common:.2f}")

    on = shot(1, face=0.05, faces=1)
    none = shot(2, face=0.0, faces=0)
    full = shot(3, face=0.6, faces=1)
    c = clips_for([on, none, full])
    a, b, d = (sel.hero_score(x, c, w)[0] for x in (on, none, full))
    check("the creator in the world beats no face", a > b, f"{a:.2f} vs {b:.2f}")
    check("...and beats a face filling the frame", a > d, f"{a:.2f} vs {d:.2f}")

    shaky = shot(4)
    steady = shot(5)
    c = clips_for([shaky, steady])
    c[shaky.clip_id]["signals"]["motion"] = [70.0] * 7
    a, b = sel.hero_score(shaky, c, w)[0], sel.hero_score(steady, c, w)[0]
    check("a thrown-around clip scores below a steady one", a < b, f"{a:.2f} vs {b:.2f}")


def duplicates() -> None:
    print("near-repeats")
    v = np.ones(8)
    a = shot(1, vec=v, quality=0.9)
    b = shot(2, vec=v, quality=0.6)
    keep, dropped = sel.dedupe([a, b])
    check("two takes of one picture within 15 min become one", dropped == 1 and keep[0].id == a.id,
          f"kept {[k.id for k in keep]}")
    c = shot(3, vec=v, quality=0.6, when=T0 + timedelta(hours=3))
    keep, dropped = sel.dedupe([a, c])
    check("the same picture hours apart is two moments", dropped == 0, f"dropped {dropped}")

    # three takes of the boba cup at cosine 0.8 inside one session: one gets in
    base = np.array([1, 0.6, 0, 0, 0, 0, 0, 0])
    takes = [shot(i, vec=base + 0.35 * np.eye(8)[4 + i], labels={"cup": 0.8}) for i in range(3)]
    other = shot(7, vec=np.eye(8)[7], labels={"stairs": 0.8})
    pool = takes + [other]
    plan = sel.choose(pool, clips_for(pool), n=4)
    ids = [p.shot.id for p in plan.picks if p.role != "hook"]
    check("look-alikes in one session yield one pick", sum(i in [t.id for t in takes] for i in ids) == 1
          and other.id in ids, f"picked {ids}")


def coverage() -> None:
    print("covering the day")
    g = [[shot(0, end=1.0)], [shot(1, end=4.0), shot(2, end=4.0)], [shot(3, end=16.0), shot(4, end=16.0),
                                                                     shot(5, end=16.0), shot(6, end=16.0)]]
    q = sel.quotas(g, 7)
    check("quota grows with the square root of footage, one each at least", q == [1, 2, 4], str(q))

    morning = [shot(i, when=T0 + timedelta(minutes=i)) for i in range(4)]
    evening = [shot(10 + i, when=T0 + timedelta(hours=9, minutes=i)) for i in range(4)]
    pool = morning + evening
    plan = sel.choose(pool, clips_for(pool), n=4)
    sess = [len(s) for s in plan.sessions]
    check("a 45-minute gap makes two sessions, both covered", len(sess) == 2 and min(sess) >= 1, str(sess))

    weak = [shot(i, quality=0.2, aesthetic=-0.8) for i in range(5)]
    plan = sel.choose(weak, clips_for(weak), n=5)
    check("weak shots don't fill a quota; the edit runs short", len(plan.picks) - len(plan.hook) == 1,
          f"{len(plan.picks) - len(plan.hook)} of 5")


def hook() -> None:
    print("the hook")
    craft = shot(0, quality=0.95, aesthetic=0.9, face=0.05, faces=1)
    moment = shot(1, quality=0.8, aesthetic=0.4, labels={"crosswalk": 0.9, "sky": 0.7})
    fill = [shot(i) for i in range(2, 6)]
    pool = [craft, moment] + fill
    c = clips_for(pool)
    c[moment.clip_id]["signals"]["contrast"] = [0.9] * 7
    plan = sel.choose(pool, c, n=6)
    check("the hook is the distinctive, punchy moment, not the best-lit selfie",
          plan.hook and plan.hook[0].shot.id == moment.id, plan.hook[0].shot.id if plan.hook else "none")


def windows() -> None:
    print("cutting on the action")
    s = shot(0, end=10.0)
    c = clips_for([s])
    c[s.clip_id]["signals"]["subject"] = [0.1] * 6 + [0.9] + [0.1] * 4
    a, b, short = sel.window(c, s, 1.0)
    check("the window starts just before the busiest second", 5.9 <= a <= 6.4 and abs(b - a - 1.0) < 1e-6,
          f"{a:.2f}-{b:.2f}")
    a2, _, _ = sel.window(c, s, 1.0)
    c[s.clip_id]["signals"]["subject"] = [0.9] + [0.1] * 10
    a3, _, _ = sel.window(c, s, 1.0)
    check("...and never in the clip's first moments", a3 >= sel.EDGE_S, f"{a3:.2f}")
    a4, b4, short = sel.window(c, shot(1, end=0.7), 1.0)
    check("a clip shorter than the beat is used whole and flagged", short and (a4, b4) == (0.0, 0.7),
          f"{a4}-{b4} short={short}")


def main() -> int:
    scoring()
    duplicates()
    coverage()
    hook()
    windows()
    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
