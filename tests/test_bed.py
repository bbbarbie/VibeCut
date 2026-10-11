"""Music by default, cuts on its beat: does the bed do what it says?

The edit is the test_board story (13 shots of 12 s, 156 s). Two synthetic
tracks: one at 123 BPM with a jump in loudness (the drop), long enough; one
too short. The bed must pick the long one, start it so the drop lands at the
end of the hook, move cuts onto the beat (the 12 s cuts are off a 0.488 s
grid, so they have to move), hold a talking shot still and duck under it,
be one turn that replays exactly and undoes whole, and the timeline's beat
grid must honour where the track starts.

    python tests/test_bed.py
"""

from __future__ import annotations

import copy
import os
import sys
import tempfile
import threading
import wave

import numpy as np

# setdefault: the index pool's workers re-import this script and must share the cache
os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-bed-"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import music as mu  # noqa: E402
from tests.test_board import CLIPS, PROPOSALS, session  # noqa: E402
from web.backend import bed, timeline  # noqa: E402

mk = lambda d: PROPOSALS  # noqa: E731
BPM = 123.0
failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def _track(path: str, seconds: float, bpm: float, loud_from: float | None, sr: int = 16000) -> None:
    t = np.arange(int(seconds * sr)) / sr
    x = 0.05 * np.sin(2 * np.pi * 220 * t)
    if loud_from is not None:
        x[t >= loud_from] *= 8
    for b in np.arange(0, seconds, 60.0 / bpm):
        i = int(b * sr)
        x[i:i + 40] += 0.5
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def cuts(board: dict) -> list[float]:
    return [it["seq_end"] for it in timeline.layout(board)][:-1]


def on_grid(times: list[float], grid: dict, tol: float = 0.03) -> int:
    period = 60.0 / grid["bpm"]
    return sum(abs(((t - grid["phase"]) / period) - round((t - grid["phase"]) / period)) * period <= tol for t in times)


def main() -> int:
    s, cat = session()
    clips = {c["id"]: c for c in CLIPS}
    before = copy.deepcopy(s.board)
    need_s = timeline.layout(s.board)[-1]["seq_end"]

    print("fingerprint")
    fp = bed.fingerprint(s.board, cat, "calm")
    check("the pace sets the tempo range", fp["bpm"] == bed.PACE_BPM["calm"], str(fp["bpm"]))
    check("an unknown pace is balanced", bed.fingerprint(s.board, cat, None)["pace"] == "balanced")
    check("the energy arc is the edit's own, resampled", len(fp["energy"]) == bed.ENERGY_POINTS)
    check("the hook is the first shot, capped", fp["hook_s"] == bed.HOOK_S[1], str(fp["hook_s"]))

    print("the pick")
    with tempfile.TemporaryDirectory() as d:
        _track(os.path.join(d, "long.wav"), need_s + 70, BPM, loud_from=24.0)   # room for the drop to be a start
        _track(os.path.join(d, "short.wav"), 60.0, BPM, loud_from=24.0)
        pool = mu.LocalFolderSource(d).list()
        check("both tracks read, with a tempo", len(pool) == 2 and all(t.bpm for t in pool),
              str([(t.title, t.bpm) for t in pool]))
        fp = bed.fingerprint(s.board, cat, "balanced")
        mx = bed.pick(fp, pool, need_s)
        check("the long track is picked; the short one can't cover the edit", mx is not None and mx["track"].title == "long",
              str(mx and mx["track"].title))
        check("it reads at the beat's tempo (half-time doubled if need be)", mx and abs(mx["bpm"] - BPM) < 1.0, str(mx and mx["bpm"]))
        check("it starts so the drop lands at the end of the hook", mx and abs(mx["drop"] - mx["in"] - fp["hook_s"]) < 0.05,
              f"drop {mx and mx['drop']:.2f} in {mx and mx['in']:.2f} hook {fp['hook_s']}")
        check("the drop is where the music jumps", mx and abs(mx["drop"] - 24.0) < 0.6, str(mx and mx["drop"]))

        print("the turn")
        talking = {s.board["beats"][1]["shots"][0]["id"]}
        ops, report = bed.ops(s.board, cat, mx, talking)
        kinds = [o["op"] for o in ops]
        check("two ops: the cuts onto the beat, then the bed", kinds == ["apply_style", "set_music"], str(kinds))
        grid = ops[0]["grid"]
        was = on_grid(cuts(before), grid)
        t = s.add({"kind": "direct", "text": bed.__name__, "ops": ops}, cat, mk)
        check("the turn applied", not t.skipped, str(t.skipped))
        now = on_grid(cuts(s.board), grid)
        # every cut but the talking shot's own end (it holds its window) is on the grid
        check("cuts moved onto the beat", now > was and now >= len(cuts(s.board)) - 1, f"{was} -> {now} of {len(cuts(s.board))}")
        check("the report counts them", report["on_beat"] >= 8, str(report))
        held = next(e for bt in s.board["beats"] for e in bt["shots"] if e["id"] in talking)
        was_e = next(e for bt in before["beats"] for e in bt["shots"] if e["id"] in talking)
        check("the talking shot kept its window", (held["start"], held["end"]) == (was_e["start"], was_e["end"]),
              f"{(held['start'], held['end'])} vs {(was_e['start'], was_e['end'])}")
        m = s.board["music"]
        check("the bed is on the board", m["track"] == mx["track"].id and m["in"] == mx["in"] and m["gain"] == bed.MUSIC_GAIN,
              str(m))
        lay = timeline.layout(s.board)
        it = next(x for x in lay if x["shot_id"] in talking)
        check("and ducks under the talking shot, nowhere else", m["duck"] == [[it["seq_start"], it["seq_end"], bed.TALK_DUCK]],
              f"{m['duck']} vs {(it['seq_start'], it['seq_end'])}")
        check("the original sound stays up front", m["original"] == 1.0)
        check("the diff says it", any("beat" in l["text"].lower() or "music" in l["text"].lower() for l in t.lines),
              " | ".join(l["text"] for l in t.lines[-3:]))

        print("the timeline's grid")
        tl = timeline.build(s.board, clips, mx["track"])
        check("the beat grid is in edit time: the track's phase less where it starts",
              tl["grid"] and abs(tl["grid"]["phase"] - ((mx["track"].meta["tempo"]["phase"] - mx["in"]) % (60 / mx["track"].bpm))) < 1e-3,
              str(tl["grid"]))
        beats = [x["t"] for x in tl["targets"] if x["type"] == "beat"]
        check("snap targets follow it", beats and abs(beats[0] - tl["grid"]["phase"]) < 1e-3, str(beats[:2]))

        print("undo")
        s.toggle(t.id, cat, mk)
        check("one undo takes the beat and the music away together", s.board.get("music") is None
              and [e["end"] - e["start"] for bt in s.board["beats"] for e in bt["shots"]]
              == [e["end"] - e["start"] for bt in before["beats"] for e in bt["shots"]])
        s.toggle(t.id, cat, mk)
        check("and back", s.board.get("music", {}).get("track") == mx["track"].id)

        print("the job")
        done = threading.Event()
        got: dict = {}

        def landed(job: bed.Job) -> None:
            got["job"] = job
            done.set()
        job = bed.start(copy.deepcopy(before), cat, "balanced", pool, need_s, set(), landed)
        check("it looks in the background", job.stage == "looking")
        done.wait(60)
        check("and lands with the ops and a plain reply", got["job"].stage == "done" and got["job"].result["ops"][1]["op"] == "set_music"
              and "Music:" in got["job"].result["reply"], got["job"].why or got["job"].result["reply"][:80])
        job2 = bed.start(copy.deepcopy(before), cat, "balanced", [p for p in pool if p.title == "short"], need_s, set(), landed)
        done.clear()
        done.wait(60)
        check("nothing long enough: says so, adds nothing", job2.stage == "nothing" and "long enough" in job2.why, job2.why)

    api()
    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


def api() -> None:
    """Through the real server: a story chosen -> the bed lands as a turn;
    the Music switch takes it away and finds it again."""
    print("through the API")
    import json
    import time
    from pathlib import Path

    from fastapi.testclient import TestClient
    from tests.test_projects import TMP as PTMP, clip, wait
    from web.backend import app as backend

    d = Path(tempfile.mkdtemp(prefix="vibecut-bed-music-"))
    _track(str(d / "long.wav"), 240.0, BPM, loud_from=24.0)
    a = clip(PTMP / "bed-a.mp4", 6, "0xff8a1e", "0x2a3440", "'325+40*sin(t)'", "2026-09-20T08:10:00")
    b = clip(PTMP / "bed-b.mp4", 7, "0x1ec8ff", "0x203028", "'120+30*t'", "2026-09-20T11:05:00")
    os.environ["VIBECUT_BED"] = "1"
    with TestClient(backend.app) as c:
        c.post("/api/projects", json={"name": "Bed"})
        c.post("/api/music/folder", json={"folder": str(d)})
        for _ in range(100):
            if c.get("/api/music/suggest").json()["status"] == "ready":
                break
            time.sleep(0.2)
        wait(c, c.post("/api/import", json={"paths": [a, b]}).json())
        c.post("/api/project/brief", json={"message": "a day", "style": {"length": "short"}, "said": "short"})
        c.post("/api/cut/approve", json={})
        r = c.post("/api/chat", json={"message": "a day", "style": {"length": "short"}})
        s = r.json()
        check("proposals built", r.status_code == 200 and s.get("proposals"), json.dumps(s)[:200])
        opt = s["proposals"]["options"][0]["key"]
        s = c.post("/api/ops", json={"ops": [{"op": "choose_option", "option": opt}], "label": "pick"}).json()
        check("choosing a story starts the hunt", s["bed"] and s["bed"]["stage"] == "looking", json.dumps(s["bed"]))
        for _ in range(300):
            s = c.get("/api/session").json()
            if s["bed"]["stage"] != "looking":
                break
            time.sleep(0.2)
        check("the bed lands as its own turn", s["bed"]["stage"] == "done" and s["turns"][-1]["text"] == backend.BED_TEXT,
              json.dumps(s["bed"]))
        check("music under the edit, from the folder", s["music"] and s["music"]["title"] == "long", json.dumps(s["music"]))
        check("the mix the preview plays has it", bool(s["mix"]))
        check("the timeline has its beat grid", s["timeline"]["grid"] and abs(s["timeline"]["grid"]["bpm"] - BPM) < 1)
        s = c.post("/api/bed", json={"on": False}).json()
        check("Music off: one turn, no track, no grid", s["music"] is None and s["timeline"]["grid"] is None
              and s["turns"][-1]["text"] == "No music")
        s = c.post(f"/api/turns/{s['turns'][-1]['id']}/toggle", json={}).json()
        check("undo brings it back", s["music"] and s["music"]["title"] == "long")

        print("the look grades the file")
        from cutgrammar import media, style as st

        def export(label: str) -> dict:
            job = c.post("/api/export", json={"music": False}).json()
            job = c.post(f"/api/export/{job['id']}/start", json={"schedule": []}).json()
            for _ in range(600):
                if job["stage"] in ("done", "error"):
                    break
                time.sleep(0.25)
                job = c.get(f"/api/export/{job['id']}").json()
            check(f"export {label} done", job["stage"] == "done", job.get("error") or "")
            return job
        s = c.post("/api/ops", json={"ops": [{"op": "set_look", "look": None}], "label": "no look"}).json()
        check("no look: the board's style has no grade to render", not (s["board"]["style"] or {}).get("look"), json.dumps(s["board"]["style"]))
        plain = export("plain")
        s = c.post("/api/ops", json={"ops": [{"op": "set_look", "look": "cozy"}], "label": "cozy"}).json()
        check("Cozy: the board's style promises its grade and its joins",
              s["board"]["style"]["look"]["pending"] and s["board"]["style"]["transitions"]["between"] == "dissolve",
              json.dumps(s["board"]["style"]))
        cozy = export("cozy")
        check("the export names the look", cozy["style"] == "Cozy", str(cozy["style"]))
        lp, lc = st.learn(media.load(plain["path"]))["look"], st.learn(media.load(cozy["path"]))["look"]
        check("and the file is warmer, by about the look's warmth", 4 <= lc["warmth"] - lp["warmth"] <= 16,
              f"warmth {lp['warmth']} -> {lc['warmth']}")
        check("same length to the frame", abs(cozy["total"] - plain["total"]) < 0.01)
        backend._close_project()


if __name__ == "__main__":
    sys.exit(main())
