"""The AI checks its own edit (selfcheck.py): does it see the cut whole, fix
only what it may, and spend only what the creator saw?

No network: OpenAI's reply is played by a stand-in, and every request it
would have received is kept.

The contact sheet: one still per shot from the middle of the seconds it
uses, sixteen to a sheet, numbered as the timeline numbers them, a strip
coloured by chapter; a shot with no picture is a dark tile and the list
says so. The list that goes with it: chapters with their seconds and share,
and the phone's hints -- a pair whose feature prints look alike is named,
a pair that doesn't is not (built to differ in that one respect), and the
same seconds of one clip used twice is named.

The fixes: drop / shorten / move become board ops on the right shots;
shortening keeps whole half-beats; a drop past a quarter of the shots, a
talking shot dropped for anything but a repeat, any drop from a tiny edit,
a "shorten" that lengthens, an unknown number or a second fix to one shot
are left out (and said where it matters).

Through the API: nothing is sent without the AI switch and the price shown;
a check is one undoable turn of kind "check" with its cost, its sheets and
its fixes; the cost is kept and counted; Stop drops the fixes and keeps the
cost; the app isn't held up while it looks; a failed check says so and
changes nothing. After Make, the check runs once inside the job and lands
as its own turn after "Made your video".

    python tests/test_selfcheck.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Its own cache, always: the test flips the AI switch (ai.json), which must
# never be a real one. Empty keys, so web/.env on a dev Mac is never read.
if __name__ == "__main__":   # the indexer's worker processes re-run this file: they keep this cache
    os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-selfcheck-")
os.environ["VIBECUT_EXPORTS"] = os.path.join(os.environ["VIBECUT_CACHE"], "out")
os.environ.setdefault("VIBECUT_BED", "0")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from tests.test_board import CLIPS, PROPOSALS, session  # noqa: E402
from web.backend import app as A  # noqa: E402
from web.backend import board as bd, llm, make, oai, selfcheck as sc, timeline  # noqa: E402
from web.backend import projects as pj  # noqa: E402

oai.ENV_FILE = llm.ENV_FILE = Path(os.environ["VIBECUT_CACHE"]) / "no.env"
TMP = Path(tempfile.mkdtemp(prefix="vibecut-selfcheck-stills-"))
failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def still(k: int, w: int = 216, h: int = 384) -> str:
    p = TMP / f"s{k}.jpg"
    if not p.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x{(k * 2654435761) % 0xffffff:06x}:s={w}x{h}",
                        "-frames:v", "1", str(p)], check=True)
    return str(p)


def answer(fixes: list[dict], summary: str = "Two shots of the same café; I kept the sharper one.",
           issues: list[dict] | None = None, finish: str = "stop") -> dict:
    return {"model": "gpt-6.1-sol", "usage": {"prompt_tokens": 7000, "completion_tokens": 2600},
            "choices": [{"finish_reason": finish, "message": {"content": json.dumps(
                {"summary": summary, "issues": issues if issues is not None else
                 [{"kind": "repeat", "shots": [2, 6], "note": "the same café twice"}], "fixes": fixes})}}]}


def fix(do: str, shot: int, seconds=None, before=None, because="repeat") -> dict:
    return {"do": do, "shot": shot, "seconds": seconds, "before": before, "because": because}


def refused(fn) -> HTTPException | None:
    try:
        fn()
    except HTTPException as e:
        return e
    return None


# --------------------------------------------------------------------------

def sheet_tests() -> None:
    print("the contact sheet")
    s, cat = session()
    items = sc.shots_of(s.board)
    check("the edit's shots, numbered in playing order", [it["n"] for it in items] == list(range(1, len(items) + 1))
          and len(items) == 13, str(len(items)))
    asked: list[float] = []
    real = sc.moment._frame
    sc.moment._frame = lambda rec, t: asked.append(t) or still(len(asked))
    try:
        paths = sc.stills_of(items, {c["id"]: c for c in CLIPS})
    finally:
        sc.moment._frame = real
    mids = [(it["src_start"] + it["src_end"]) / 2 for it in items]
    check("one still per shot, from the middle of the seconds it uses", asked == mids, f"{asked[:3]} vs {mids[:3]}")

    chapters = sc.chapters_of(s.board)
    many = (items * 2)[:20]
    many = [{**it, "n": k + 1} for k, it in enumerate(many)]
    pics, dark = sc.sheets(many, (paths * 2)[:20], "tall", chapters)
    check("sixteen shots to a sheet", len(pics) == 2)
    img = decode(pics[0])
    w, h = sc.TILE["vertical"]
    want_w = sc.PAD + 8 * (w + sc.PAD)
    check("vertical stills, eight across, two rows", img.shape[1] == want_w
          and img.shape[0] == sc.PAD + 2 * (h + sc.STRIP_H + sc.PAD), str(img.shape))
    strip = lambda j: img[sc.PAD + h + 4: sc.PAD + h + sc.STRIP_H - 4, sc.PAD + j * (w + sc.PAD) + 2: sc.PAD + j * (w + sc.PAD) + w - 2]  # noqa: E731
    check("each still is numbered (white letters on its strip)", all((strip(j) > 230).all(axis=2).sum() > 30 for j in range(8)))
    hue = lambda j: np.median(strip(j).reshape(-1, 3), axis=0)  # noqa: E731
    first = [it["beat_id"] for it in many[:8]]
    same = [j for j in range(1, 8) if first[j] == first[0]]
    diff = [j for j in range(1, 8) if first[j] != first[0]]
    check("one colour per chapter, a new colour for the next",
          same and diff and all(np.abs(hue(j) - hue(0)).max() < 24 for j in same)
          and all(np.abs(hue(j) - hue(0)).max() > 40 for j in diff), f"{first}")
    check("every shot had a picture", not dark)

    paths2 = list(paths)
    paths2[3] = None
    paths2[5] = str(TMP / "gone.jpg")
    pics, dark = sc.sheets(items, paths2, "wide", chapters)
    img = decode(pics[0])
    w, h = sc.TILE["wide"]
    check("wide stills, four across", img.shape[1] == sc.PAD + 4 * (w + sc.PAD), str(img.shape))
    check("a shot with no picture, or whose picture is gone, is named", dark == {4, 6}, str(dark))
    text = sc.legend(items, chapters, cat, set(), "wide", 60, None, dark)
    check("and the list says its tile is dark", "#4 · " in text and "no picture" in text.split("#4 · ")[1].split("\n")[0])


def decode(jpeg: bytes) -> np.ndarray:
    p = TMP / "probe.jpg"
    p.write_bytes(jpeg)
    info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip().split(",")
    w, h = int(info[0]), int(info[1])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3)


def legend_tests() -> None:
    print("the list that goes with it")
    s, cat = session()
    items = sc.shots_of(s.board)
    chapters = sc.chapters_of(s.board)
    text = sc.legend(items, chapters, cat, set(), "tall", 50, 120.0)
    total = items[-1]["seq_end"]
    check("the whole cut, its asked length and its beat", f"{len(items)} shots, {total:.1f} s" in text
          and "about 50 s" in text and "120 BPM" in text)
    market = [it for it in items if it["beat_title"] == "Market"]
    secs = market[-1]["seq_end"] - market[0]["seq_start"]
    check("each chapter with its shots, seconds and share",
          f"“Market”: #{market[0]['n']}-#{market[-1]['n']}, {len(market)} shots, {secs:.1f} s ({100 * secs / total:.0f}% of the video)" in text)
    check("each shot with its clip, labels and seconds", "#1 · Morning · 12.0 s on screen · of 12.0 s filmed · hotel0000001.MOV @ 0:00" in text)

    # two shots that differ only in how alike their feature prints are
    a, b = items[0], items[4]
    sa, sb_ = cat.shots[a["shot_id"]], cat.shots[b["shot_id"]]
    keep = (sa.vec, sb_.vec)
    try:
        sa.vec = np.array([1.0, 0, 0, 0])
        sb_.vec = np.array([0.9, np.sqrt(1 - 0.81), 0, 0])
        near = sc.hints([a, b], cat)
        sb_.vec = np.array([0.5, np.sqrt(0.75), 0, 0])
        far = sc.hints([a, b], cat)
    finally:
        sa.vec, sb_.vec = keep
    check("a look-alike pair is named, with its score", near == [f"#{a['n']} and #{b['n']} look alike to the phone (0.90)"], str(near))
    check("the same pair, not alike, is not", far == [], str(far))
    twice = [a, {**a, "n": 9, "key": "again", "src_start": a["src_start"] + 2, "src_end": a["src_end"] + 2}]
    check("the same seconds of one clip twice is named", any("same seconds" in h for h in sc.hints(twice, cat)))
    talk = sc.legend(items, chapters, cat, {items[2]["shot_id"]}, "tall", None, None)
    check("someone talking to the camera is marked", "someone talks to the camera" in talk.split(f"#{items[2]['n']} · ")[1].split("\n")[0])


def fixes_tests() -> None:
    print("the fixes")
    s, cat = session()
    items = sc.shots_of(s.board)
    by_n = {it["n"]: it for it in items}
    ops, left = sc.fixes_to_ops({"fixes": [fix("drop", 6)]}, items, set())
    check("drop: that shot goes", ops == [{"op": "drop_shot", "shot": by_n[6]["key"]}] and not left, json.dumps(ops))
    ops, left = sc.fixes_to_ops({"fixes": [fix("drop", k, because="drags") for k in (2, 3, 5, 7, 9)]}, items, set())
    check("never more than a quarter of the shots", len(ops) == 3 and len(left) == 2 and "too much" in left[0], f"{len(ops)} {left}")
    talking = {by_n[4]["shot_id"]}
    ops, left = sc.fixes_to_ops({"fixes": [fix("drop", 4, because="drags")]}, items, talking)
    check("someone talking to the camera is kept when it only drags", not ops and "talks to the camera" in left[0], str(left))
    ops, _ = sc.fixes_to_ops({"fixes": [fix("drop", 4, because="repeat")]}, items, talking)
    check("...and dropped when it repeats another shot", ops and ops[0]["op"] == "drop_shot")
    ops, _ = sc.fixes_to_ops({"fixes": [fix("drop", 2)]}, items[:5], set())
    check("nothing is dropped from an edit of five shots", not ops)

    ops, _ = sc.fixes_to_ops({"fixes": [fix("shorten", 3, seconds=5.0, because="drags")]}, items, set())
    it = by_n[3]
    check("shorten: its end is trimmed to that length", ops == [{"op": "trim", "shot": it["key"], "edge": "out",
                                                                  "to": round(it["src_start"] + 5.0, 3)}], json.dumps(ops))
    ops, _ = sc.fixes_to_ops({"fixes": [fix("shorten", 3, seconds=4.3, because="drags")]}, items, set(), period=0.5)
    check("with a beat: whole half-beats (4.3 s -> 4.25 s at 120 BPM)", ops and abs(ops[0]["to"] - (it["src_start"] + 4.25)) < 1e-6,
          json.dumps(ops))
    ops, _ = sc.fixes_to_ops({"fixes": [fix("shorten", 3, seconds=0.1, because="drags")]}, items, set(), period=0.5)
    check("never below 0.6 s (on the beat: 0.75 s)", ops and abs(ops[0]["to"] - (it["src_start"] + 0.75)) < 1e-6, json.dumps(ops))
    ops, _ = sc.fixes_to_ops({"fixes": [fix("shorten", 3, seconds=30, because="drags")]}, items, set())
    check("a shorten that lengthens is left out", not ops)
    slow = [{**x, "speed": 2.0} if x["n"] == 3 else x for x in items]
    ops, _ = sc.fixes_to_ops({"fixes": [fix("shorten", 3, seconds=2.0, because="drags")]}, slow, set())
    check("a sped-up shot: its source seconds follow its speed", ops and abs(ops[0]["to"] - (it["src_start"] + 4.0)) < 1e-6)

    ops, _ = sc.fixes_to_ops({"fixes": [fix("move", 12, before=1, because="opening")]}, items, set())
    check("move: before that shot, in its chapter", ops == [{"op": "move_shot", "shot": by_n[12]["key"],
                                                              "beat": by_n[1]["beat_id"], "before": by_n[1]["key"]}], json.dumps(ops))
    ops, _ = sc.fixes_to_ops({"fixes": [fix("move", 5, before=6), fix("move", 5, before=5)]}, items, set())
    check("a move to where it already is does nothing", not ops)
    ops, _ = sc.fixes_to_ops({"fixes": [fix("drop", 1), fix("move", 12, before=1, because="opening")]}, items, set())
    check("a move next to a shot being dropped is left out", ops == [{"op": "drop_shot", "shot": by_n[1]["key"]}], json.dumps(ops))
    ops, _ = sc.fixes_to_ops({"fixes": [fix("drop", 99), fix("drop", 2), fix("shorten", 2, seconds=1)]}, items, set())
    check("unknown numbers and a second fix to one shot are left out", ops == [{"op": "drop_shot", "shot": by_n[2]["key"]}])

    # they apply, and undo as one
    t = s.add({"kind": "check", "text": sc.CheckError.__name__, "ops": sc.fixes_to_ops(
        {"fixes": [fix("drop", 6), fix("shorten", 3, seconds=5, because="drags"), fix("move", 12, before=1, because="opening")]},
        items, set())[0]}, cat, lambda d: PROPOSALS)
    after = sc.shots_of(s.board)
    check("on the board: one gone, one shorter, one first", len(after) == 12 and not t.skipped
          and after[0]["key"] == by_n[12]["key"] and abs((after[3]["seq_end"] - after[3]["seq_start"]) - 5.0) < 1e-6,
          f"{t.skipped} {[x['key'] for x in after[:4]]}")
    s.toggle(t.id, cat, lambda d: PROPOSALS)
    check("one Undo takes all of it back", [x["key"] for x in sc.shots_of(s.board)] == [x["key"] for x in items])


def estimate_tests() -> None:
    print("the price, before it's asked")
    e30, e60 = sc.estimate(30, "gpt-6.1-sol"), sc.estimate(60, "gpt-6.1-sol")
    check("a few cents, more for a longer edit", 0.01 < e30 < e60 < 0.1, f"{e30:.3f} {e60:.3f}")
    check("an unknown model is priced at the dearest", sc.estimate(30, "mystery") >= e30)


# --------------------------------------------------------------------------

def api_tests() -> None:
    print("through the app")
    s, cat = session()
    A.SESSION = s
    A.CATALOG["cat"] = cat
    A.CLIPS.clear()
    A.CLIPS.update({c["id"]: c for c in CLIPS})
    A._make_proposals = lambda d: PROPOSALS
    A._session = lambda: {}   # the fixture clips have no files to read sound from
    A._save = lambda: None
    A.WORKFLOW.state = "story"
    A.PROJECT["p"] = pj.Project(id="check", name="Check")
    sent: list[dict] = []
    replies: list[dict] = []

    def stand_in(url, body, headers):
        sent.append(body)
        return replies.pop(0)
    real_post, real_stills = oai._post, sc.stills_of
    oai._post = stand_in
    sc.stills_of = lambda items, clips: [still(k % 7) for k in range(len(items))]   # the fixture clips have no index frames
    by_n = {it["n"]: it for it in sc.shots_of(s.board)}
    try:
        e = refused(lambda: A.api_check(A.CheckReq(ai_ok=0.05)))
        check("no key: refused, says so", e is not None and e.status_code == 409 and "no AI key" in e.detail and not sent)
        os.environ["OPENAI_API_KEY"] = "sk-test"
        oai.switch(False)
        check("AI off: the estimate is nothing", A.api_check_estimate()["dollars"] == 0 and not A.api_check_estimate()["on"])
        e = refused(lambda: A.api_check(A.CheckReq(ai_ok=0.05)))
        check("AI off: refused, says to turn it on", e is not None and "turn AI on" in e.detail and not sent)
        oai.switch(True)
        est = A.api_check_estimate()
        check("on: priced for this edit before anything is sent", est["on"] and est["shots"] == 13
              and est["dollars"] == round(sc.estimate(13), 3) and not sent, json.dumps(est))
        e = refused(lambda: A.api_check(A.CheckReq()))
        check("without the price it was shown: refused, nothing sent", e is not None and e.status_code == 409 and not sent)

        replies.append(answer([fix("drop", 6), fix("shorten", 3, seconds=5, because="drags")]))
        n_turns = len(s.turns)
        A.api_check(A.CheckReq(ai_ok=est["dollars"]))
        body = sent[-1]
        parts = body["messages"][-1]["content"]
        imgs = [p for p in parts if p["type"] == "image_url"]
        check("one request: the list, then the sheet at high detail", len(sent) == 1 and parts[0]["type"] == "text"
              and parts[0]["text"].startswith("The cut: 13 shots") and len(imgs) == 1
              and imgs[0]["image_url"]["detail"] == "high")
        check("its own instructions and a strict schema", body["messages"][0]["content"] == sc.SYSTEM
              and body["response_format"]["json_schema"]["name"] == "edit_check"
              and body["response_format"]["json_schema"]["strict"])
        t = A.SESSION.turns[-1]
        keys = [x["key"] for x in sc.shots_of(A.SESSION.board)]
        check("one turn, of its own kind, that did it", len(A.SESSION.turns) == n_turns + 1 and t.kind == "check"
              and by_n[6]["key"] not in keys and not t.skipped, f"{t.kind} {t.skipped}")
        check("its reply says what it looked at and why", t.reply.startswith("I looked over all 13 shots")
              and "same café" in t.reply, t.reply)
        paid = round(oai.cost({"prompt_tokens": 7000, "completion_tokens": 2600}, "gpt-6.1-sol"), 4)
        check("the cost is on the turn", t.cost == paid, str(t.cost))
        ev = A.PROJECT["p"].events[-1]
        check("kept with the project and in the running total", ev["kind"] == "check" and ev["cost"] == paid
              and ev["fixes"] == 2 and A._ai_spent() == paid)
        check("the sheet it looked at is kept, and can be shown", t.sheets and sc.sheet_path(t.sheets[0]) is not None
              and sc.sheet_path("../../etc/passwd") is None)
        back = pj.turn_from_dict(json.loads(json.dumps(pj.turn_to_dict(t))))
        check("a restart keeps its kind, cost and sheets", back.kind == "check" and back.cost == t.cost and back.sheets == t.sheets)
        A.SESSION.toggle(t.id, cat, lambda d: PROPOSALS)
        check("Undo takes all of it back", [x["key"] for x in sc.shots_of(A.SESSION.board)] == list(by_n[k]["key"] for k in sorted(by_n)))
        A.SESSION.toggle(t.id, cat, lambda d: PROPOSALS)
        A.SESSION.toggle(t.id, cat, lambda d: PROPOSALS)     # leave it undone

        replies.append(answer([], summary="It holds up.", issues=[]))
        A.api_check(A.CheckReq(ai_ok=est["dollars"]))
        t = A.SESSION.turns[-1]
        check("a cut that holds up: said, nothing changed", t.kind == "check" and not t.ops and "holds up" in t.reply)

        import threading
        free: list[bool] = []

        def thinking(url, body, headers):
            def try_lock() -> None:
                got = A.LOCK.acquire(blocking=False)
                free.append(got)
                if got:
                    A.LOCK.release()
            th = threading.Thread(target=try_lock)
            th.start()
            th.join()
            A.api_chat_stop(A.StopReq(rid="check-1"))      # Stop pressed while it looks
            return stand_in(url, body, headers)
        oai._post = thinking
        replies.append(answer([fix("drop", 2)]))
        n_turns, before = len(A.SESSION.turns), A._ai_spent()
        snap = json.dumps(A.SESSION.board, sort_keys=True, default=str)
        out = A.api_check(A.CheckReq(ai_ok=est["dollars"], rid="check-1"))
        check("the app isn't held up while it looks", free == [True])
        check("Stop: nothing changes", out.get("stopped") and len(A.SESSION.turns) == n_turns
              and json.dumps(A.SESSION.board, sort_keys=True, default=str) == snap)
        check("what it cost is still counted, and said", out["stop_cost"] and A._ai_spent() > before)
        oai._post = stand_in

        replies.append(answer([], finish="length"))
        before = A._ai_spent()
        A.api_check(A.CheckReq(ai_ok=est["dollars"]))
        t = A.SESSION.turns[-1]
        check("a failed check says so, changes nothing, and counts what it cost",
              t.kind == "check" and not t.ops and "couldn't check" in t.reply and "cut off" in t.reply
              and A._ai_spent() > before, t.reply)

        print("after Make")
        landed: list[dict] = []
        board_seen: list[int] = []

        def check_fn(ops_, period):
            trial = bd.Session()
            trial.add({"kind": "direct", "text": "made", "ops": json.loads(json.dumps(ops_))}, cat, lambda d: PROPOSALS)
            board_seen.append(len(sc.shots_of(trial.board)))
            return {"ops": [], "reply": "I looked over all of it.", "sheets": [], "usage": {"cost": 0.04}}
        job = make.start({c["id"]: c for c in CLIPS}, None, "tall", "balanced", None, "a day", 40.0, None, None,
                         None, on_done=landed.append, want_music=False, check=check_fn)
        import time
        for _ in range(200):
            if landed:
                break
            time.sleep(0.05)
        check("the job looks at the finished cut once, before it's done", landed and job.stage == "done"
              and board_seen and board_seen[0] >= 3 and job.result.get("check", {}).get("reply"), job.error or str(board_seen))
        landed.clear()
        job = make.start({c["id"]: c for c in CLIPS}, None, "tall", "balanced", None, "a day", 40.0, None, None,
                         None, on_done=landed.append, want_music=False)
        for _ in range(200):
            if landed:
                break
            time.sleep(0.05)
        check("no agreed AI cost, no look", landed and job.stage == "done" and "check" not in job.result
              and len(board_seen) == 1, job.error or "")
    finally:
        oai._post, sc.stills_of = real_post, real_stills
        oai.switch(False)
        os.environ["OPENAI_API_KEY"] = ""


def main() -> int:
    sheet_tests()
    legend_tests()
    fixes_tests()
    estimate_tests()
    api_tests()
    print(f"\n{'all passed' if not failures else f'{len(failures)} failed: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
