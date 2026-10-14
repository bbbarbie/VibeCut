"""Opening + ending: does the switch open on the moment it should, end on
the shot it should, and finish the song on a phrase?

A day of 12 s shots in filming order. One market shot is built to be the
hook (well made and moving); a sunset shot near the end is built to be the
closer (still, a calm view). Discrimination: take away what makes each one
stand out and the pick moves; make the hook shot a talking one and it is
never chosen. With music under the edit (test_bed's synthetic 123 BPM
track with a drop), the edit must end RING_S after a whole number of
phrases from the drop, the drop must still land at the end of the first
shot, and the music fades over the ring. Off puts everything back.

    python tests/test_bookends.py
"""

from __future__ import annotations

import copy
import os
import sys
import tempfile

import numpy as np

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-bookends-"))
os.environ.setdefault("VIBECUT_BED", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import music as mu  # noqa: E402
from tests.test_bed import BPM, _track  # noqa: E402
from web.backend import bed, bookends, timeline  # noqa: E402
from web.backend import board as bd  # noqa: E402

failures: list[str] = []
HOOK, CLOSER = "market000001:2", "sunset000001:0"


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def _clip(cid, hour, labels, n=1, q=0.6, act=15.0, special=None):
    special = special or {}
    return {
        "id": cid, "name": f"{cid}.MOV", "duration": 12.0 * n,
        "capture_time": f"2026-05-02T{hour:02d}:00:00+0900", "gps": None,
        "shots": [{
            "index": i, "start": i * 12.0, "end": (i + 1) * 12.0, "thumb": f"shot{i:03d}.jpg",
            "best_t": i * 12.0 + 6.0, "quality": special.get(i, {}).get("q", q), "aesthetic": None,
            "utility": False, "labels": [[l, 0.8] for l in special.get(i, {}).get("labels", labels)],
            "faces": 0, "face_area": 0.0, "activity": special.get(i, {}).get("act", act),
            "embedding": [1.0 if j == i % 8 else 0.0 for j in range(8)],
        } for i in range(n)],
    }


def clips(hook=True, closer=True):
    return [
        _clip("hotel0000001", 8, ["structure", "bedroom"], 3),
        _clip("market000001", 10, ["food", "market"], 4, special={2: {"q": 0.8, "act": 40.0}} if hook else None),
        _clip("temple000001", 13, ["temple", "structure"], 3),
        _clip("sunset000001", 18, ["sunset", "ocean"] if closer else ["street"], 1, act=2.0 if closer else 25.0),
        _clip("dinner000001", 19, ["food", "restaurant"], 2, act=25.0),
    ]


def board_of(cs) -> dict:
    beats = [{"id": f"b{k}", "title": c["id"][:6], "detail": "",
              "shots": [{"id": f"{c['id']}:{s['index']}", "start": s["start"], "end": s["end"]} for s in c["shots"]]}
             for k, c in enumerate(cs)]
    return {"option": "time", "name": "As it happened", "structure": "", "beats": beats}


def session(cs):
    s = bd.Session()
    cat = bd.Catalog.from_clips(cs)
    b = board_of(cs)
    s.add({"kind": "direct", "text": "pick", "ops": [{"op": "choose_option", "snapshot": b}]}, cat, lambda d: None)
    s.add({"kind": "direct", "text": "captions", "ops": [
        {"op": "add_overlay", "kind": "caption", "text": "10:00 am · market", "shot": HOOK, "at": 0.4, "dur": 2.5},
        {"op": "add_overlay", "kind": "caption", "text": "8:00 am", "shot": "hotel0000001:0", "at": 0.4, "dur": 2.5}]},
        cat, lambda d: None)
    return s, cat


def seq(board):
    return [bd.key(e) for bt in board["beats"] for e in bt["shots"]]


def main() -> int:
    print("the picks")
    cs = clips()
    s, cat = session(cs)
    check("the hook is the moving, well-made shot", bookends.pick(s.board, cat, set())[0] == HOOK,
          str(bookends.pick(s.board, cat, set())))
    check("the closer is the still sunset", bookends.pick(s.board, cat, set())[1] == CLOSER)
    s2, cat2 = session(clips(hook=False))
    check("without what makes it stand out, the hook moves", bookends.pick(s2.board, cat2, set())[0] != HOOK,
          str(bookends.pick(s2.board, cat2, set())[0]))
    s3, cat3 = session(clips(closer=False))
    check("a busy street shot is not the closer", bookends.pick(s3.board, cat3, set())[1] != CLOSER,
          str(bookends.pick(s3.board, cat3, set())[1]))
    check("a talking shot is never the hook", bookends.pick(s.board, cat, {HOOK})[0] not in (HOOK, None),
          str(bookends.pick(s.board, cat, {HOOK})[0]))

    print("the turn (no music)")
    before = copy.deepcopy(s.board)
    ops, said = bookends.turn(s.board, cat, set(), "short")
    t = s.add({"kind": "direct", "text": bookends.TEXT, "ops": ops, "reply": said}, cat, lambda d: None)
    check("it applied", not t.skipped, str(t.skipped))
    order = seq(s.board)
    check("the hook opens it", order[0] == HOOK, str(order[:3]))
    check("the closer ends it", order[-1] == CLOSER, str(order[-3:]))
    check("nothing is shown twice", len(order) == len(set(order)) == len(seq(before)))
    first = s.board["beats"][0]["shots"][0]
    check("a short's hook holds 3 s, around its best frame", abs(first["end"] - first["start"] - 3.0) < 0.01
          and first["start"] <= 30.0 <= first["end"], str(first))
    check("the hook's out-of-order clock caption is gone, the day's first stays",
          [o["text"] for o in s.board.get("overlays", [])] == ["8:00 am"], str(s.board.get("overlays")))
    check("the switch reads on", bookends.is_on(s.turns))
    s.toggle(t.id, cat, lambda d: None)
    check("off puts every shot back", s.board["beats"] == before["beats"] and s.board.get("overlays") == before["overlays"])
    check("and reads off", not bookends.is_on(s.turns))

    print("the song's end")
    with tempfile.TemporaryDirectory() as d:
        s, cat = session(cs)
        need = timeline.layout(s.board)[-1]["seq_end"]
        _track(os.path.join(d, "long.wav"), need + 70, BPM, loud_from=24.0)
        pool = mu.LocalFolderSource(d).list()
        fp = bed.fingerprint(s.board, cat, "balanced")
        mx = bed.pick(fp, pool, need)
        check("a track is picked", mx is not None)
        plain, _ = bed.ops(s.board, cat, mx, set())
        s.add({"kind": "direct", "text": "Music and the beat", "ops": plain}, cat, lambda d: None)
        m = s.board["music"]
        check("the bed remembers its tempo and drop", m.get("bpm") == mx["bpm"] and m.get("drop") == mx["drop"], str(m))
        period = 60.0 / mx["bpm"]

        def phrases(board):
            mm = board["music"]
            end = timeline.layout(board)[-1]["seq_end"]
            # 16 beats from the drop when the closer can reach one, else 8
            k = (end - bookends.RING_S - (mm["drop"] - mm["in"])) / (8 * period)
            return k, abs(k - round(k)) * 8 * period

        k0, off0 = phrases(s.board)
        before = copy.deepcopy(s.board)
        ops, said = bookends.turn(s.board, cat, set(), "tall",
                                  lambda trial: bed.relay(trial, cat, m, mx["track"], set()))
        t = s.add({"kind": "direct", "text": bookends.TEXT, "ops": ops, "reply": said}, cat, lambda d: None)
        check("it applied", not t.skipped, str(t.skipped))
        k1, off1 = phrases(s.board)
        check("the edit ends a ring after a phrase from the drop", off1 < 0.02, f"{k1:.3f} half phrases (was {k0:.3f})")
        first = timeline.layout(s.board)[0]["seq_end"]
        mm = s.board["music"]
        check("the drop still lands at the end of the first shot", abs(mm["drop"] - mm["in"] - first) < 0.02,
              f"drop-in {mm['drop'] - mm['in']:.2f} first {first:.2f}")
        check("the music fades over the ring", mm["fade_out"] == bookends.RING_S, str(mm["fade_out"]))
        check("the reply says so", "phrase" in said, said)
        check("the edit still ends on the closer", seq(s.board)[-1] == CLOSER)
        s.toggle(t.id, cat, lambda d: None)
        check("off puts the music back too", s.board["music"] == before["music"] and s.board["beats"] == before["beats"])

        # the music lands after the switch is on: the bed's own turn ends on the phrase
        s, cat = session(cs)
        ops, _ = bookends.turn(s.board, cat, set(), "tall")
        s.add({"kind": "direct", "text": bookends.TEXT, "ops": ops}, cat, lambda d: None)
        fp = bed.fingerprint(s.board, cat, "balanced")
        mx = bed.pick(fp, pool, timeline.layout(s.board)[-1]["seq_end"])
        more, report = bed.ops(s.board, cat, mx, set(), end=True)
        s.add({"kind": "direct", "text": "Music and the beat", "ops": more}, cat, lambda d: None)
        k2, off2 = phrases(s.board)
        check("music that lands later ends on a phrase too", off2 < 0.02 and report.get("ending") in ("phrase", "half phrase"),
              f"{k2:.3f} {report.get('ending')}")

    print("through the app")
    from web.backend import app as A
    s, cat = session(cs)
    A.SESSION, A.CATALOG["cat"], A.PLAN["plan"] = s, cat, None
    A.CLIPS.clear()
    A.CLIPS.update({c["id"]: c for c in cs})
    A._make_proposals = lambda d: None
    real_session, A._session = A._session, lambda: {}
    before, n = copy.deepcopy(s.board), len(s.turns)
    check("off until asked", not bookends.is_on(A.SESSION.turns))
    A.api_bookends(A.BookendsReq(on=True))
    check("on: one turn", len(A.SESSION.turns) == n + 1 and seq(A.SESSION.board)[0] == HOOK
          and seq(A.SESSION.board)[-1] == CLOSER, str(seq(A.SESSION.board)))
    A.api_bookends(A.BookendsReq(on=True))
    check("asking twice adds no second turn", len(A.SESSION.turns) == n + 1)
    A.api_bookends(A.BookendsReq(on=False))
    check("off: back as it was", A.SESSION.board["beats"] == before["beats"] and not bookends.is_on(A.SESSION.turns))
    A._session = real_session

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


def test_bookends() -> None:
    assert main() == 0


if __name__ == "__main__":
    np.seterr(all="ignore")
    sys.exit(main())
