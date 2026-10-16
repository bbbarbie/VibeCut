"""Your profile: asked once after the first export, the start of the next video.

Not asked before an export, asked after the first one, never again after a
skip; the email is the only thing typed and must look like one. The answers
start the next video (pace, captions and their style, the transition at
every cut, the look), and what's changed in Frames moves the profile -- but
only when there is one.

    python tests/test_profile.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-profile-"))
os.environ.setdefault("VIBECUT_EXPORTS", os.path.join(os.environ["VIBECUT_CACHE"], "out"))
os.environ.setdefault("VIBECUT_BED", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend import looks, profile as creator  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def main() -> int:
    print("on its own")
    tmp = Path(tempfile.mkdtemp(prefix="vibecut-profile-unit-")) / "profile.json"
    p = creator.load(tmp)
    check("nothing saved: blank, not asked", p["email"] is None and not creator.should_ask(p))
    p = creator.exported(tmp)
    check("after the first export: asked", creator.should_ask(p))
    try:
        creator.create("not an email", {}, tmp)
        check("a non-email is refused", False)
    except creator.ProfileError:
        check("a non-email is refused", True)
    try:
        creator.create("a@b.co", {"pace": "frantic"}, tmp)
        check("an unknown pick is refused", False)
    except creator.ProfileError:
        check("an unknown pick is refused", True)
    check("a refused profile wasn't saved", creator.load(tmp)["email"] is None)
    creator.skip(tmp)
    check("skipped: never asked again", not creator.should_ask(creator.exported(tmp)))
    check("skipped: nothing is learned", creator.learn("pace", "fast", "x", tmp) is None
          and creator.load(tmp)["pace"] is None)
    tmp.write_text("{broken")
    check("a broken file is a blank profile", creator.load(tmp)["email"] is None)
    p = creator.create("sam@example.com", {"kind": "lesson", "pace": "calm", "transition": "zoom",
                                           "captions": "outlined"}, tmp)
    d = creator.defaults(p)
    check("a lesson is captioned with what's said", d["captions"] == "transcribe", json.dumps(d))
    check("the rest start the next video", d["pace"] == "calm" and d["template"] == "outlined"
          and d["transition"] == "zoom", json.dumps(d))
    board = {"beats": [{"shots": [{}, {}]}], "overlays": [{"id": "o1"}]}
    ops = creator.ops_for(board, d)
    check("as one caption style and one transition for every cut",
          ops == [{"op": "overlay_style", "template": "outlined"}, {"op": "set_transition", "all": True, "kind": "zoom"}],
          json.dumps(ops))
    check("no captions on the story: no caption style", creator.ops_for({**board, "overlays": []}, d)
          == [{"op": "set_transition", "all": True, "kind": "zoom"}])
    p = creator.create("sam@example.com", {"kind": "vlog", "captions": "none"}, tmp)
    check("no captions wins over the kind", creator.defaults(p)["captions"] == "none")
    check("picks not asked again are kept", p["transition"] == "zoom", json.dumps(p))
    check("the looks it knows are the looks there are", set(creator.FIELDS["look"]) == set(looks.all_looks()))
    p = creator.forget(tmp)
    check("forget: gone, and not asked again", p["email"] is None and not creator.should_ask(p))

    print("through the API")
    from fastapi.testclient import TestClient
    from tests.test_projects import TMP as PTMP, clip, wait
    from web.backend import app as backend
    a = clip(PTMP / "prof-a.mp4", 6, "0xff8a1e", "0x2a3440", "'325+40*sin(t)'", "2026-09-20T08:10:00")
    b = clip(PTMP / "prof-b.mp4", 7, "0x1ec8ff", "0x203028", "'120+30*t'", "2026-09-20T11:05:00")

    def story(c, look: str | None = None) -> dict:
        s = c.post("/api/brief/auto", json={"format": "wide", **({"look": look} if look else {})}).json()
        c.post("/api/cut/approve", json={})
        s = c.post("/api/chat", json={"message": s["brief"]["message"], "style": s["brief"]["style"]}).json()
        opt = s["proposals"]["options"][0]["key"]
        return c.post("/api/ops", json={"ops": [{"op": "choose_option", "option": opt}], "label": "pick"}).json()

    with TestClient(backend.app) as c:
        check("before any export: not asked", c.get("/api/profile").json()["ask"] is False)
        c.post("/api/projects", json={"name": "First"})
        wait(c, c.post("/api/import", json={"paths": [a, b]}).json())
        story(c, "cozy")
        job = c.post("/api/export", json={"music": False}).json()
        s = c.post(f"/api/export/{job['id']}/start", json={"schedule": []}).json()
        t0 = time.time()
        while s["stage"] not in ("done", "error", "cancelled") and time.time() - t0 < 240:
            time.sleep(0.5)
            s = c.get(f"/api/export/{job['id']}").json()
        check("the export finished", s["stage"] == "done", s.get("error") or s["stage"])
        c.get(f"/api/export/{job['id']}")     # polled again: still one export
        r = c.get("/api/profile").json()
        check("after the first export: asked, once counted", r["ask"] is True and r["exports"] == 1, json.dumps(r))
        check("a bad email comes back as a message", c.post("/api/profile", json={"email": "sam"}).status_code == 422)
        r = c.post("/api/profile", json={"email": "sam@example.com", "kind": "vlog", "pace": "calm",
                                         "transition": "dip_black", "captions": "outlined"}).json()
        check("made: not asked again", r["email"] == "sam@example.com" and r["ask"] is False, json.dumps(r))
        backend._close_project()

        c.post("/api/projects", json={"name": "Second"})
        wait(c, c.post("/api/import", json={"paths": [a, b]}).json())
        creator.learn("look", "quiet", "a test")
        r = c.get("/api/brief/setup").json()
        check("the popup's look starts at the profile's", r["look"] == "quiet", r["look"])
        s = story(c)
        st = s["brief"]["style"]
        check("the next video starts at the profile's pace", st["pace"] == "calm" and "as you like" in s["brief"]["tempo"],
              json.dumps(st))
        check("with its look", st["look"] == "quiet", json.dumps(st))
        check("the caption style is the profile's", s["overlays"]["style"].get("template") == "outlined",
              json.dumps(s["overlays"]["style"])[:200])
        tr = (s["board"].get("style") or {}).get("transitions") or {}
        check("every cut is the profile's transition", tr.get("between") == "dip_black" and tr.get("within") == "dip_black",
              json.dumps(tr))
        texts = [t["text"] for t in s["turns"]] if "turns" in s else []
        check("one undoable turn says so", "Your style" in texts, json.dumps(texts))

        c.post("/api/pace", json={"pace": "fast"})
        check("pace changed in Frames: the profile follows", creator.load()["pace"] == "fast")
        c.post("/api/ops", json={"ops": [{"op": "set_look", "look": "hype"}], "label": "Hype"})
        c.post("/api/ops", json={"ops": [{"op": "overlay_style", "template": "pop", "enter": "stamp"}], "label": "Pop"})
        s = c.post("/api/ops", json={"ops": [{"op": "set_transition", "all": True, "kind": "light_leak"}], "label": "Leak"}).json()
        p = creator.load()
        check("a look, a caption style and animation, a transition for every cut: learnt",
              p["look"] == "hype" and p["captions"] == "pop" and p["enter"] == "stamp" and p["transition"] == "light_leak",
              json.dumps(p)[:300])
        c.post("/api/captions", json={"on": False})
        check("captions off: remembered", creator.load()["captions"] == "none")
        check("what was learned is listed", len(c.get("/api/profile").json()["learned"]) >= 3)
        backend._close_project()

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
