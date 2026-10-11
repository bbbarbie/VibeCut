"""Two picks up front -- the frame and the look -- and they must reach the file.

The frame: what was filmed upright is suggested upright, a small shoot is a
short; the pick overrides the footage; a short's length is capped. The
look: picked before anything is cut, it dresses the story (set_look) even
when there are no captions, and the Frames chip can change the frame later.

    python tests/test_format.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time

# setdefault: the index pool's workers re-import this script and must share the cache
os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-format-"))
os.environ.setdefault("VIBECUT_EXPORTS", os.path.join(os.environ["VIBECUT_CACHE"], "out"))
os.environ.setdefault("VIBECUT_BED", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_board import PROPOSALS, session  # noqa: E402
from web.backend import brief, export, looks  # noqa: E402

mk = lambda d: PROPOSALS  # noqa: E731
failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def main() -> int:
    print("the frame")
    check("the looks the brief knows are the looks there are", set(brief.LOOK_IDS) == set(looks.all_looks()),
          str(sorted(looks.all_looks())))
    check("upright footage, a small shoot: a short", brief.suggest_format(0.9, 120) == "short")
    check("upright footage, a big shoot: a vertical vlog", brief.suggest_format(0.9, 900) == "tall")
    check("sideways footage: wide", brief.suggest_format(0.2, 900) == "wide")
    marks = brief.length_marks(900.0, "a day in my life")
    check("a short is the Short mark, capped", brief.length_for("short", marks) <= brief.SHORT_MAX_S
          and brief.length_for("short", marks) <= marks["marks"][0]["seconds"], str(brief.length_for("short", marks)))
    check("the others take the suggestion", brief.length_for("wide", marks) == marks["seconds"])
    items = [{"clip_id": "a", "seq_start": 0, "seq_end": 10}]
    clips = {"a": {"path": "/nowhere.mp4", "width": 1080, "height": 1920}}
    check("the pick overrides the footage", export.frame_size(items, clips, "wide") == {"w": 1920, "h": 1080}
          and export.frame_size(items, clips, "short") == {"w": 1080, "h": 1920})
    check("no pick: the footage decides", export.frame_size(items, clips) == {"w": 1080, "h": 1920})
    check("only the three frames are kept", (brief.clean_style({"format": "wide", "look": "hype"}) or {}) == {"format": "wide", "look": "hype"}
          and "format" not in (brief.clean_style({"format": "square"}) or {}))

    print("the look")
    s, cat = session()
    ops, _ = brief.caption_ops(s.board, cat, "none", "A day", look="hype")
    check("no captions, but the look picked up front still dresses the video", ops == [{"op": "set_look", "look": "hype"}], str(ops))
    ops, _ = brief.caption_ops(s.board, cat, "describe", "A day in Tokyo", look="film")
    check("with captions: that look, then the words", ops[0] == {"op": "set_look", "look": "film"} and len(ops) > 1)
    ops, _ = brief.caption_ops(s.board, cat, "describe", "A day in Tokyo", look="bold")
    check("the old caption-question answers still map", ops[0] == {"op": "set_look", "look": "hype"})

    print("through the API")
    from fastapi.testclient import TestClient
    from tests.test_projects import TMP as PTMP, clip, wait
    from web.backend import app as backend
    a = clip(PTMP / "fmt-a.mp4", 6, "0xff8a1e", "0x2a3440", "'325+40*sin(t)'", "2026-09-20T08:10:00")
    b = clip(PTMP / "fmt-b.mp4", 7, "0x1ec8ff", "0x203028", "'120+30*t'", "2026-09-20T11:05:00")
    with TestClient(backend.app) as c:
        c.post("/api/projects", json={"name": "Frame"})
        wait(c, c.post("/api/import", json={"paths": [a, b]}).json())
        r = c.get("/api/brief/setup").json()
        check("the popup gets the footage's own defaults: sideways clips suggest wide",
              r["format"] == "wide" and r["look"] == "cozy" and len(r["looks"]) == 7 and len(r["formats"]) == 3, json.dumps(r)[:200])
        s = c.post("/api/brief/auto", json={"format": "short", "look": "hype"}).json()
        check("the picks are the brief", s["brief"]["style"]["format"] == "short" and s["brief"]["style"]["look"] == "hype"
              and s["brief"]["style"]["seconds"] <= brief.SHORT_MAX_S, json.dumps(s["brief"]))
        check("and the brief says so in words", "Short" in s["brief"]["said"] and "Hype" in s["brief"]["said"], s["brief"]["said"])
        check("the stage is vertical though the clips are sideways", s["timeline"]["frame"] == {"w": 1080, "h": 1920}, json.dumps(s["timeline"]["frame"]))
        check("a wrong pick is refused", c.post("/api/brief/auto", json={"format": "square"}).status_code == 422)
        c.post("/api/cut/approve", json={})
        s = c.post("/api/chat", json={"message": s["brief"]["message"], "style": s["brief"]["style"]}).json()
        opt = s["proposals"]["options"][0]["key"]
        s = c.post("/api/ops", json={"ops": [{"op": "choose_option", "option": opt}], "label": "pick"}).json()
        check("the story wears the look picked up front", s["overlays"]["look"]["id"] == "hype", json.dumps(s["overlays"].get("look"))[:120])
        check("and the board's style carries its joins and grade for export", s["board"]["style"]["name"] == "Hype"
              and s["board"]["style"]["look"], json.dumps(s["board"]["style"])[:160])
        s = c.post("/api/format", json={"format": "wide"}).json()
        check("the chip changes the frame later", s["timeline"]["frame"] == {"w": 1920, "h": 1080} and s["brief"]["style"]["format"] == "wide")
        job = c.post("/api/export", json={"music": False}).json()
        check("the export is cut to that frame", job["size"] == {"w": 1920, "h": 1080}, json.dumps(job["size"]))
        c.post(f"/api/export/{job['id']}/cancel", json={})
        backend._close_project()

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
