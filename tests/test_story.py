"""The story editor: a model plans the video as chapters (story.py, oai.py).

No network: OpenAI's reply is played by a stand-in. Unit: nothing is called
without the key *and* the creator's yes (VIBECUT_STORY_AI=1); a call's cost
comes from its usage; an answer is checked against what was offered (unknown
numbers, repeats and the hook inside a chapter are dropped, lengths are held
to their job's range and to what was filmed); payoffs sit on whole beats.
Chapter titles are their own overlay kind with their own look. Through the
API: Make with the stand-in lands chapters as the board's parts, a titled
heading per chapter, and the cost in the reply; a broken answer falls back
to the rules' edit and says so.

    python tests/test_story.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-story-"))
os.environ.setdefault("VIBECUT_EXPORTS", os.path.join(os.environ["VIBECUT_CACHE"], "out"))
os.environ.setdefault("VIBECUT_BED", "0")
os.environ["VIBECUT_REMIX_JUDGE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def shot(i: int, dur: float):
    from web.backend import storyboard as sb
    return sb.Shot(id=f"c{i}:0", clip_id=f"c{i}", clip_name=f"IMG_{i}", index=0, start=0.0, end=dur, thumb="",
                   quality=0.7, aesthetic=None, utility=False, when=datetime(2026, 10, 14, 9) + timedelta(minutes=10 * i),
                   gps=None, labels={"food": 0.8}, faces=0, face_area=0.0, activity=0.3, vec=np.ones(4) / 2, order=i)


def answer_for(n: int, hook: int | None = None) -> dict:
    half = max(1, (n - 1) // 2)
    nums = [k for k in range(1, n + 1) if k != hook]
    a, b = nums[:half], nums[half:]
    return {"video_title": "A day out", "hook": hook, "chapters": [
        {"title": "Morning Routine", "subtitle": "slow start", "look": "script",
         "shots": [{"n": k, "role": "setup" if j == 0 else "step", "seconds": 1.2} for j, k in enumerate(a)]},
        {"title": "OOTD", "subtitle": "trying on everything", "look": "spaced",
         "shots": [{"n": k, "role": "payoff" if j == len(b) - 1 else "step", "seconds": 1.5} for j, k in enumerate(b)]},
    ]}


def reply(ans: dict, prompt=9000, out=2500) -> dict:
    return {"model": "gpt-6.1-sol", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(ans)}}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": out}}


def unit() -> None:
    from web.backend import oai, overlays as ov, story

    print("the yes to spend")
    for k in ("OPENAI_API_KEY", "VIBECUT_STORY_AI", "OPENAI_MODEL"):
        os.environ.pop(k, None)
    real_env = oai.ENV_FILE
    oai.ENV_FILE = Path(tempfile.mkdtemp()) / ".env"
    check("no key: off", not oai.enabled())
    oai.ENV_FILE.write_text("ANTHROPIC_API_KEY=x\nOPENAI_API_KEY=sk-test\n")
    check("a key alone is not a yes", oai.has_key() and not oai.enabled())
    oai.ENV_FILE.write_text("OPENAI_API_KEY=sk-test\nVIBECUT_STORY_AI=1\n")
    check("key + VIBECUT_STORY_AI=1: on", oai.enabled())
    oai.ENV_FILE = real_env

    print("what a call costs")
    c = oai.cost({"prompt_tokens": 10_000, "completion_tokens": 3000}, "gpt-6.1-sol")
    check("sol: 10k in + 3k out = $0.05", abs(c - 0.05) < 1e-9, f"{c}")
    check("an unknown model is priced at the dearest row", oai.cost({"prompt_tokens": 1e6}, "mystery") == oai.DEAREST[0])
    est = story.estimate(60, "gpt-6.1-sol")
    check("a 60-moment plan is estimated at a few cents", 0.02 < est < 0.15, f"${est:.3f}")

    print("the answer, checked")
    cands = [shot(i, 6.0 if i != 2 else 0.9) for i in range(8)]
    ans = answer_for(8, hook=8)
    ans["chapters"][0]["shots"] += [{"n": 99, "role": "step", "seconds": 1}, {"n": 1, "role": "step", "seconds": 1},
                                    {"n": 8, "role": "step", "seconds": 1}]
    ans["chapters"][1]["shots"][0]["seconds"] = 30.0
    ans["chapters"].append({"title": "Empty", "subtitle": "", "look": "bold", "shots": [{"n": 1, "role": "payoff", "seconds": 3}]})
    plan, chapters, title = story.plan_from(ans, cands, {}, "tall")
    ids = [p.shot.id for p in plan.picks]
    check("unknown numbers, repeats and the hook twice are dropped", len(ids) == len(set(ids)) == 8 and "c7:0" == ids[0], str(ids))
    check("a chapter left with nothing is dropped", [c["title"] for c in chapters] == ["Morning Routine", "OOTD"])
    lo, hi = story.ROLE_S["tall"]["step"]
    p30 = plan.sessions[1][0]
    check("a length outside its job is held to the range", abs(p30.duration - hi) < 1e-6, f"{p30.duration}")
    short = next(p for p in plan.picks if p.shot.id == "c2:0")
    check("never longer than it was filmed", short.duration <= 0.9 + 1e-6)
    check("payoffs on whole beats (hero), the rest on half-beats",
          plan.sessions[1][-1].role == "hero" and plan.sessions[0][0].role == "filler" and plan.hook[0].role == "hook")
    check("parts are named by the chapters", plan.titles == ["Morning Routine", "OOTD"] and title == "A day out")
    try:
        story.plan_from({"video_title": "", "hook": None, "chapters": []}, cands, {}, "tall")
        check("an empty plan is refused", False)
    except story.StoryError:
        check("an empty plan is refused", True)

    print("chapter titles have their own look")
    hs = story.heading_ops(plan, chapters)
    check("one heading per chapter, at its start", [h["beat"] for h in hs] == ["r1", "r2"] and hs[0]["look"] == "script")
    b = {"beats": [{"id": "r1", "title": "x", "shots": [{"id": "c0:0", "start": 0, "end": 3}]}], "overlays": []}
    ov.add(b, dict(hs[0]), lambda: "o1")
    o = b["overlays"][0]
    check("a heading keeps its words, line under it and look", o["kind"] == "heading" and o["sub"] == "slow start" and o["look"] == "script")
    try:
        ov.add(b, {"op": "add_overlay", "kind": "caption", "text": "hi", "look": "script", "beat": "r1"}, lambda: "o2")
        check("only a chapter title takes a look", False)
    except ov.OverlayError:
        check("only a chapter title takes a look", True)
    ov.edit(b, {"overlay": "o1", "look": "serif"})
    check("its look can be changed", b["overlays"][0]["look"] == "serif")

    print("the request")
    os.environ["OPENAI_API_KEY"] = "sk-test"
    seen = {}

    def post(url, body, headers):
        seen.update(body=body, headers=headers)
        return reply(answer_for(3))
    got, usage = oai.ask_json("sys", [{"type": "text", "text": "hi"}], story.SCHEMA, "story_plan", post=post)
    check("strict json schema, low-detail frames, cost read back",
          seen["body"]["response_format"]["json_schema"]["strict"] and usage["cost"] > 0 and got["chapters"])
    check("frames go at low detail", oai.image(b"\xff\xd8")["image_url"]["detail"] == "low")
    try:
        oai.ask_json("s", [], story.SCHEMA, "x", post=lambda *a: {"choices": [{"finish_reason": "length", "message": {"content": "{"}}]})
        check("a cut-off answer is an error", False)
    except oai.OAIError:
        check("a cut-off answer is an error", True)
    os.environ.pop("OPENAI_API_KEY")


def api() -> None:
    from cutgrammar import music as mu
    from fastapi.testclient import TestClient
    from tests.test_bed import BPM, _track
    from tests.test_projects import TMP as PTMP, clip, wait
    from web.backend import app as backend, bed, oai

    print("through the API, with a stand-in for OpenAI")
    cols = ["0xff8a1e", "0x1ec8ff", "0xd0ff1e", "0xff1e8a", "0x1effa0", "0xffe01e", "0x8a1eff", "0xff4d1e"]
    bgs = ["0x2a3440", "0x203028", "0x302028", "0x282030", "0x203030", "0x303020", "0x202838", "0x382820"]
    xs = ["'325+40*sin(t)'", "'120+30*t'", "'200+20*sin(2*t)'", "'60+50*t'", "'400-30*t'", "'250+60*sin(t/2)'", "'90+25*t'", "'300-40*sin(t)'"]
    clips = [clip(PTMP / f"st-{i}.mp4", 7 + i % 3, cols[i], bgs[i], xs[i], f"2026-09-20T{8 + (16 * i) // 60:02d}:{(16 * i) % 60:02d}:00") for i in range(8)]
    d = Path(tempfile.mkdtemp(prefix="vibecut-story-music-"))
    _track(str(d / "beat.wav"), 240.0, BPM, loud_from=24.0)
    pool = mu.LocalFolderSource(str(d)).list()
    real_cand, real_post = bed.candidates, oai._post
    bed.candidates = lambda pace, own, progress=None: (pool, "a test track")
    calls = []

    def fake(url, body, headers):
        n = sum(1 for p in body["messages"][1]["content"] if p["type"] == "text" and p["text"].startswith("#"))
        calls.append(n)
        return reply(answer_for(n, hook=n))
    oai._post = fake
    os.environ["OPENAI_API_KEY"] = "sk-test"

    def make(c, fmt="tall"):
        job = c.post("/api/make", json={"format": fmt, "look": "cozy"}).json()
        for _ in range(600):
            if job["stage"] in ("done", "error"):
                break
            time.sleep(0.25)
            job = c.get(f"/api/make/{job['id']}").json()
        return job

    try:
        with TestClient(backend.app) as c:
            c.post("/api/projects", json={"name": "Story"})
            wait(c, c.post("/api/import", json={"paths": clips}).json())
            for rec in backend.CLIPS.values():
                for sh in rec.get("shots", []):
                    sh["utility"] = False
            os.environ.pop("VIBECUT_STORY_AI", None)
            job = make(c)
            check("without the yes, nothing is sent", job["stage"] == "done" and not calls, job.get("error") or "")
            c.post("/api/undo")
            os.environ["VIBECUT_STORY_AI"] = "1"
            job = make(c)
            check("with the yes, one call", job["stage"] == "done" and len(calls) == 1, job.get("error") or str(calls))
            s = c.get("/api/session").json()
            titles = [b["title"] for b in s["board"]["beats"]]
            check("the parts are the chapters, after the hook", titles == ["Hook", "Morning Routine", "OOTD"], str(titles))
            items = s["overlays"]["items"]
            heads = [o for o in items if o["kind"] == "heading"]
            check("a designed title per chapter, each with its line under it",
                  [(o["text"], o["look"]) for o in heads] == [("Morning Routine", "script"), ("OOTD", "spaced")]
                  and heads[1]["sub"] == "trying on everything", json.dumps(heads)[:200])
            check("no clock-time stop lines on a planned edit", not any(o["kind"] == "part" for o in items))
            last = s["turns"][-1] if s.get("turns") else {}
            said = json.dumps(s)
            check("the reply names the model and the cost", "planned it as 2 chapters (cost $" in said, last.get("reply", "")[:160])
            ev = backend.PROJECT["p"].events[-1]
            check("the cost is kept with the project", ev.get("ai", {}).get("cost", 0) > 0, json.dumps(ev.get("ai")))
            c.post("/api/undo")
            oai._post = lambda url, body, headers: reply({"video_title": "", "hook": None, "chapters": []})
            job = make(c)
            s = c.get("/api/session").json()
            check("a useless answer falls back to the rules, and says so",
                  job["stage"] == "done" and "story plan didn't work" in json.dumps(s), job.get("error") or "")
    finally:
        bed.candidates, oai._post = real_cand, real_post
        for k in ("OPENAI_API_KEY", "VIBECUT_STORY_AI"):
            os.environ.pop(k, None)


def main() -> int:
    unit()
    api()
    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
