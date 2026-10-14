"""Opening + ending: does the switch open on a quick look at the day, end on
the shot it should, and finish the song on a phrase?

A day of 12 s shots in filming order; the story uses the middle 6 s of each
(as a rough cut would). One market shot is built to be the day's liveliest
(well made and moving); a sunset shot near the end is built to be the
closer (still, a calm view). Checks: the preview has as many moments as
the video's length asks for, one per stretch of the day, in filming order,
never two from one clip, never the stretch the story shows; the lively
shot is the market's flash, and when it is made ordinary the pick moves;
the date (and place) caption starts after the first second. Without what
makes the sunset an ending, it isn't the closer. With music under the edit
(test_bed's synthetic 123 BPM track with a drop) every preview cut is on
the beat, the drop lands as the story starts, the edit ends RING_S after a
whole number of half-phrases from the drop and the music fades over the
ring. Off puts everything back.

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
LIVELY, CLOSER = "market000001:2", "sunset000001:0"


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def _clip(k, cid, hour, labels, n=1, q=0.6, act=15.0, special=None):
    special = special or {}
    return {
        "id": cid, "name": f"{cid}.MOV", "duration": 12.0 * n,
        "capture_time": f"2026-05-02T{hour:02d}:00:00+0900", "gps": None,
        "shots": [{
            "index": i, "start": i * 12.0, "end": (i + 1) * 12.0, "thumb": f"shot{i:03d}.jpg",
            "best_t": i * 12.0 + 6.0, "quality": special.get(i, {}).get("q", q), "aesthetic": None,
            "utility": False, "labels": [[l, 0.8] for l in special.get(i, {}).get("labels", labels)],
            "faces": 0, "face_area": 0.0, "activity": special.get(i, {}).get("act", act),
            # every shot its own look: no two are look-alikes
            "embedding": [1.0 if j == 4 * k + i else 0.0 for j in range(24)],
        } for i in range(n)],
    }


def clips(lively=True, closer=True):
    return [
        _clip(0, "hotel0000001", 8, ["structure", "bedroom"], 3),
        _clip(1, "market000001", 10, ["food", "market"], 4, special={2: {"q": 0.8, "act": 40.0}} if lively else None),
        _clip(2, "temple000001", 13, ["temple", "structure"], 3),
        _clip(3, "sunset000001", 18, ["sunset", "ocean"] if closer else ["street"], 1, act=2.0 if closer else 25.0),
        _clip(4, "dinner000001", 19, ["food", "restaurant"], 2, act=25.0),
    ]


def board_of(cs) -> dict:
    beats = [{"id": f"b{k}", "title": c["id"][:6], "detail": "",
              "shots": [{"id": f"{c['id']}:{s['index']}", "start": s["start"] + 3, "end": s["start"] + 9} for s in c["shots"]]}
             for k, c in enumerate(cs)]
    return {"option": "time", "name": "As it happened", "structure": "", "beats": beats}


def session(cs):
    s = bd.Session()
    cat = bd.Catalog.from_clips(cs)
    s.add({"kind": "direct", "text": "pick", "ops": [{"op": "choose_option", "snapshot": board_of(cs)}]}, cat, lambda d: None)
    s.add({"kind": "direct", "text": "captions", "ops": [
        {"op": "add_overlay", "kind": "caption", "text": "8:00 am", "shot": "hotel0000001:0", "at": 0.4, "dur": 2.5}]},
        cat, lambda d: None)
    return s, cat


def story(board):
    return [bd.key(e) for bt in board["beats"] if not bt.get("preview") for e in bt["shots"]]


def flashes(board):
    pv = bookends.preview_of(board)
    return pv["shots"] if pv else []


def main() -> int:
    print("how many moments")
    check("a short gets a taste, a vlog more, a long one up to 12",
          [bookends.count(t) for t in (30, 60, 180, 400, 900, 3600)] == [3, 4, 6, 7, 9, 12],
          str([bookends.count(t) for t in (30, 60, 180, 400, 900, 3600)]))

    print("the preview")
    cs = clips()
    s, cat = session(cs)
    before = copy.deepcopy(s.board)
    total = timeline.layout(s.board)[-1]["seq_end"]
    op = bookends.preview_op(s.board, cat)
    got = [x["id"] for x in op["shots"]]
    check("as many moments as the length asks for", len(got) == bookends.count(total), f"{len(got)} for {total:.0f} s")
    check("never two from one clip", len({g.split(':')[0] for g in got}) == len(got), str(got))
    when = [cat.shots[g].when for g in got]
    check("in filming order, from across the day", when == sorted(when) and when[0].hour == 8 and when[-1].hour >= 18,
          str([w.hour for w in when]))
    check("the market's flash is its liveliest shot", LIVELY in got, str(got))
    used = {e["id"]: (e["start"], e["end"]) for bt in before["beats"] for e in bt["shots"]}
    check("no flash shows the stretch the story uses",
          all(x["end"] <= used[x["id"]][0] - bookends.PAD_S + 1e-6 or x["start"] >= used[x["id"]][1] + bookends.PAD_S - 1e-6
              for x in op["shots"]), str(op["shots"][:2]))
    u0 = op["shots"][0]["end"] - op["shots"][0]["start"]
    check("an even rhythm without music, long enough to read its line",
          all(abs(x["end"] - x["start"] - u0) < 1e-3 for x in op["shots"]) and len(got) * u0 >= bookends.MIN_PREVIEW_S - 1e-3,
          f"{len(got)} x {u0:.2f} s")
    s2, cat2 = session(clips(lively=False))
    other = [x["id"] for x in bookends.preview_op(s2.board, cat2)["shots"]]
    check("made ordinary, the market's flash moves to another shot", LIVELY not in other, str(other))

    print("the closer")
    check("the still sunset", bookends.closer_key(s.board, cat) == CLOSER)
    s3, cat3 = session(clips(closer=False))
    check("a busy street shot is not the closer", bookends.closer_key(s3.board, cat3) != CLOSER,
          str(bookends.closer_key(s3.board, cat3)))

    print("the two switches (no music)")
    ops, said = bookends.turn(s.board, cat, "opening", "Kyoto")
    t = s.add({"kind": "direct", "text": bookends.TEXTS["opening"], "ops": ops, "reply": said}, cat, lambda d: None)
    check("it applied", not t.skipped, str(t.skipped))
    check("Opening alone: the preview opens it", s.board["beats"][0].get("preview") and len(flashes(s.board)) == len(got))
    check("and the story is exactly as it was", story(s.board) == story(before), str(story(s.board)[-3:]))
    check("Ending reads off", bookends.is_on(s.turns, "opening") and not bookends.is_on(s.turns, "ending"))
    ops2, said2 = bookends.turn(s.board, cat, "ending")
    t2 = s.add({"kind": "direct", "text": bookends.TEXTS["ending"], "ops": ops2, "reply": said2}, cat, lambda d: None)
    check("Ending: the closer moves to the end, nothing else", story(s.board)[-1] == CLOSER
          and sorted(story(s.board)) == sorted(story(before)) and flashes(s.board) and "ends on" in said2,
          str(story(s.board)[-3:]))
    check("Ending makes no preview of its own", not any(o["op"] == "preview" for o in ops2))
    s.toggle(t2.id, cat, lambda d: None)
    check("Ending off: the closer goes back, the preview stays",
          story(s.board) == story(before) and flashes(s.board))
    cap = [o for o in s.board["overlays"] if o["anchor"].get("id") == bookends.PREVIEW]
    check("date and place over the preview, from 1 s in",
          len(cap) == 1 and cap[0]["text"] == "May 2 · Kyoto" and cap[0]["at"] == bookends.CAPTION_AT_S, str(cap))
    check("the story's own captions stay", any(o["text"] == "8:00 am" for o in s.board["overlays"]))
    check("the reply says what it did", "quick look at the day" in said, said)
    s.toggle(t.id, cat, lambda d: None)
    check("Opening off puts every shot back", s.board["beats"] == before["beats"] and s.board.get("overlays") == before["overlays"])
    check("and both read off", not bookends.is_on(s.turns, "opening") and not bookends.is_on(s.turns, "ending"))

    print("the song")
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

        def halves(board):
            mm = board["music"]
            end = timeline.layout(board)[-1]["seq_end"]
            k = (end - bookends.RING_S - (mm["drop"] - mm["in"])) / (8 * period)
            return k, abs(k - round(k)) * 8 * period

        def preview_on_beat(board):
            mm = board["music"]
            lay = timeline.layout(board)
            keys = {bd.key(e) for e in flashes(board)}
            cuts = [it["seq_end"] for it in lay if it["key"] in keys]
            phase = mm["drop"] - mm["in"]
            return all(abs((c - phase) / period - round((c - phase) / period)) * period < 0.02 for c in cuts)

        before = copy.deepcopy(s.board)
        ops, said = bookends.turn(s.board, cat, "opening", None,
                                  lambda trial: bed.relay(trial, cat, m, mx["track"], set(), True, False), period)
        t = s.add({"kind": "direct", "text": bookends.TEXTS["opening"], "ops": ops, "reply": said}, cat, lambda d: None)
        m1 = s.board["music"]
        check("Opening with music: the song still fades as before", m1["fade_out"] == bed.FADE_OUT_S, str(m1["fade_out"]))
        ops2, said = bookends.turn(s.board, cat, "ending", None,
                                   lambda trial: bed.relay(trial, cat, m1, mx["track"], set(), True, True), period)
        t2 = s.add({"kind": "direct", "text": bookends.TEXTS["ending"], "ops": ops2, "reply": said}, cat, lambda d: None)
        check("both applied", not t.skipped and not t2.skipped, str(t.skipped + t2.skipped))
        u = flashes(s.board)[0]["end"] - flashes(s.board)[0]["start"]
        check("each flash is whole beats of the song", abs(u / period - round(u / period)) < 1e-3 and 0.4 < u < 1.1
              and len(flashes(s.board)) * u >= bookends.MIN_PREVIEW_S,
              f"{u:.3f} s, period {period:.3f}")
        check("every preview cut is on the beat", preview_on_beat(s.board))
        mm = s.board["music"]
        start = bookends.opening_end(s.board)
        check("the drop lands as the story starts", abs(mm["drop"] - mm["in"] - start) < 0.02,
              f"drop-in {mm['drop'] - mm['in']:.2f} story at {start:.2f}")
        k1, off1 = halves(s.board)
        check("the edit ends a ring after a phrase from the drop", off1 < 0.02, f"{k1:.3f} half phrases")
        check("the music fades over the ring", mm["fade_out"] == bookends.RING_S, str(mm["fade_out"]))
        check("the edit still ends on the closer", story(s.board)[-1] == CLOSER)
        s.toggle(t2.id, cat, lambda d: None)
        s.toggle(t.id, cat, lambda d: None)
        check("both off puts the music back too", s.board["music"] == before["music"] and s.board["beats"] == before["beats"])

        # the music lands after the switch is on: the bed's own turn re-cuts the preview and ends on a phrase
        s, cat = session(cs)
        for which in ("opening", "ending"):
            ops, _ = bookends.turn(s.board, cat, which, "Kyoto")
            s.add({"kind": "direct", "text": bookends.TEXTS[which], "ops": ops}, cat, lambda d: None)
        fp = bed.fingerprint(s.board, cat, "balanced")
        check("the music's hook waits for the preview", abs(fp["hook_s"] - bookends.opening_end(s.board)) < 0.01,
              f"{fp['hook_s']} vs {bookends.opening_end(s.board)}")
        mx = bed.pick(fp, pool, timeline.layout(s.board)[-1]["seq_end"])
        more, report = bed.ops(s.board, cat, mx, set(), True, True)
        s.add({"kind": "direct", "text": "Music and the beat", "ops": more}, cat, lambda d: None)
        mm = s.board["music"]
        k2, off2 = halves(s.board)
        check("music that lands later: preview on the beat, drop at the story, phrase at the end",
              preview_on_beat(s.board) and abs(mm["drop"] - mm["in"] - bookends.opening_end(s.board)) < 0.02
              and off2 < 0.02, f"{k2:.3f} {report.get('ending')}")
        cap = [o for o in s.board["overlays"] if o["anchor"].get("id") == bookends.PREVIEW]
        length = sum(x["end"] - x["start"] for x in flashes(s.board))
        check("the caption still fits the re-cut preview", cap and abs(cap[0]["at"] + cap[0]["dur"] - length) < 0.02,
              f"{cap and cap[0]['dur']} vs {length:.2f}")

    print("through the app")
    from web.backend import app as A
    s, cat = session(cs)
    A.SESSION, A.CATALOG["cat"], A.PLAN["plan"] = s, cat, None
    A.CLIPS.clear()
    A.CLIPS.update({c["id"]: c for c in cs})
    A._make_proposals = lambda d: None
    real_session, A._session = A._session, lambda: {}
    before, n = copy.deepcopy(s.board), len(s.turns)
    check("both off until asked", not bookends.is_on(A.SESSION.turns, "opening") and not bookends.is_on(A.SESSION.turns, "ending"))
    A.api_bookends(A.BookendsReq(part="opening", on=True))
    check("Opening on: one turn, the preview first", len(A.SESSION.turns) == n + 1
          and A.SESSION.board["beats"][0].get("preview") and story(A.SESSION.board) == story(before))
    A.api_bookends(A.BookendsReq(part="opening", on=True))
    check("asking twice adds no second turn", len(A.SESSION.turns) == n + 1)
    A.api_bookends(A.BookendsReq(part="ending", on=True))
    check("Ending on: its own turn, the closer last", len(A.SESSION.turns) == n + 2
          and story(A.SESSION.board)[-1] == CLOSER, str(story(A.SESSION.board)[-3:]))
    A.api_bookends(A.BookendsReq(part="opening", on=False))
    check("Opening off: the preview goes, the ending stays", not bookends.preview_of(A.SESSION.board)
          and story(A.SESSION.board)[-1] == CLOSER and bookends.is_on(A.SESSION.turns, "ending"))
    A.api_bookends(A.BookendsReq(part="ending", on=False))
    check("Ending off: back as it was", A.SESSION.board["beats"] == before["beats"])
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
