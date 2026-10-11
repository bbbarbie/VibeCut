"""Does a project survive a restart exactly as it was left?

Through the real API: create a project, import two synthetic clips, approve
the rough cut, build proposals from a brief, pick one, make an edit, undo a
turn -- then throw the server's memory away, reopen the project from disk,
and check that the board, the timeline, the log, the brief and the gate are
the same. Also: the dashboard's list, rename, delete, and that nothing can
be edited while no project is open.

Needs ffmpeg. Takes ~10 s.

    python tests/test_projects.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TMP = Path(tempfile.mkdtemp(prefix="vibecut-projects-"))
# setdefault, not set: the index pool spawns workers that re-import this
# script, and they must see the same cache directory as the server.
os.environ.setdefault("VIBECUT_CACHE", str(TMP / "cache"))
os.environ.setdefault("VIBECUT_EXPORTS", str(TMP / "out"))
os.environ.setdefault("VIBECUT_BED", "0")      # no music hunt online from a test

from fastapi.testclient import TestClient  # noqa: E402

from web.backend import app as backend  # noqa: E402
from web.backend import projects as pj  # noqa: E402

SCENE = ("color=c={bg}:s=800x450:d={d}:r=30,drawgrid=w=18:h=18:t=3:c=0xe0e8f0@0.9[bg];"
         "color=c={col}:s=150x150:d={d}:r=30[box];[bg][box]overlay=x={x}:y=150[c];[c]crop=640:360:x=80:y=45")


def clip(path: Path, d: float, col: str, bg: str, x: str, when: str) -> str:
    args = ["-f", "lavfi", "-i", SCENE.format(d=d, col=col, bg=bg, x=x),
            "-f", "lavfi", "-i", f"anoisesrc=d={d}:c=pink:r=16000:a=0.02",
            "-metadata", f"creation_time={when}", "-c:v", "libx264", "-preset", "ultrafast", "-g", "15",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)
    return str(path)


def wait(client: TestClient, job: dict) -> dict:
    for _ in range(300):
        if job["stage"] in ("done", "error"):
            return job
        time.sleep(0.2)
        job = client.get(f"/api/jobs/{job['id']}").json()
    raise RuntimeError("import never finished")


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    print("building fixtures...")
    a = clip(TMP / "a.mp4", 6, "0xff8a1e", "0x2a3440", "'325+40*sin(t)'", "2026-09-20T08:10:00")
    b = clip(TMP / "b.mp4", 7, "0x1ec8ff", "0x203028", "'120+30*t'", "2026-09-20T11:05:00")

    with TestClient(backend.app) as c:
        # the dashboard, empty; nothing may be edited before a project is open
        r = c.get("/api/projects").json()
        check("no projects at first", r["projects"] == [] and r["open"] is None, json.dumps(r["projects"]))
        check("capabilities are reported", {"llm", "speech", "vision", "links"} <= set(r["capabilities"]))
        check("import needs an open project", c.post("/api/import", json={"paths": [a]}).status_code == 409)

        r = c.post("/api/projects", json={"name": "Tokyo weekend"}).json()
        pid = r["project"]["id"]
        check("project created and open", r["project"]["name"] == "Tokyo weekend" and r["session"]["project"]["id"] == pid)

        job = wait(c, c.post("/api/import", json={"paths": [a, b, str(TMP / "missing.mp4")]}).json())
        s = c.get("/api/session").json()
        check("two clips indexed", job["done"] == 2 and s["project"]["clips"] == 2, f"{job['done']} / {s['project']['clips']}")
        check("the missing file is reported, not dropped",
              any("missing.mp4" in (e.get("path") or "") for e in s["import_errors"]), json.dumps(s["import_errors"]))
        check("stops at the gate", s["workflow"]["state"] == "cut-review", s["workflow"]["state"])
        check("dashboard stage is brief until described", s["project"]["stage"] == "brief", s["project"]["stage"])

        s = c.post("/api/project/brief", json={"message": "a day in the city", "style": {"length": "short"}, "said": "short"}).json()
        check("brief kept on the project", s["brief"]["message"] == "a day in the city" and s["project"]["stage"] == "cut")

        c.post("/api/cut/approve", json={})
        s = c.post("/api/chat", json={"message": "a day in the city", "style": {"length": "short", "pace": "quick", "opening": "hook"}}).json()
        check("proposals built without a key", s["proposals"] is not None and len(s["proposals"]["options"]) >= 2)
        opt = s["proposals"]["options"][0]["key"]
        s = c.post("/api/ops", json={"ops": [{"op": "choose_option", "option": opt}], "label": "pick"}).json()
        first = s["board"]["beats"][0]["shots"][0]["key"]
        s = c.post("/api/ops", json={"ops": [{"op": "drop_shot", "shot": first}], "label": "You removed a shot"}).json()
        s = c.post("/api/ops", json={"ops": [{"op": "retitle_beat", "beat": s["board"]["beats"][0]["id"], "title": "Coffee"}], "label": "rename"}).json()
        undone = s["turns"][-2]["id"]
        s = c.post(f"/api/turns/{undone}/toggle", json={}).json()
        board, total, turns = s["board"], s["timeline"]["total"], [(t["id"], t["undone"], t["text"]) for t in s["turns"]]
        check("an edit was made and one undone", any(t["undone"] for t in s["turns"]) and board is not None)
        check("stage is story", s["project"]["stage"] == "story", s["project"]["stage"])

        # rename, a second project, the list
        r = c.patch(f"/api/projects/{pid}", json={"name": "Tokyo, day one"}).json()
        check("renamed", r["project"]["name"] == "Tokyo, day one")
        r = c.post("/api/projects", json={"name": ""}).json()
        second = r["project"]["id"]
        check("a new project starts empty and is open", r["session"]["timeline"]["total"] == 0 and r["project"]["clips"] == 0)
        check("no name asked: it's a New video until its clips name it", r["project"]["name"] == "New video" and pj.load(second).auto_name)
        check("a name given or typed later is kept", not pj.load(pid).auto_name)
        rows = {p["id"]: p for p in c.get("/api/projects").json()["projects"]}
        check("the closed project is listed with its snapshot",
              rows[pid]["clips"] == 2 and rows[pid]["stage"] == "story" and rows[pid]["board"]["parts"] == len(board["beats"])
              and rows[pid]["duration"] == 13.0, json.dumps(rows[pid]))

        # the server forgets everything; the project comes back from disk
        backend._close_project()
        s = c.post(f"/api/projects/{pid}/open", json={}).json()["session"]
        check("board identical after reopen", json.dumps(s["board"], sort_keys=True) == json.dumps(board, sort_keys=True))
        check("timeline identical after reopen", s["timeline"]["total"] == total, f"{s['timeline']['total']} vs {total}")
        check("log identical after reopen", [(t["id"], t["undone"], t["text"]) for t in s["turns"]] == turns)
        check("brief and gate kept", s["brief"]["message"] == "a day in the city" and s["workflow"]["state"] in ("story", "styling"))
        check("undo still works after reopen",
              c.post(f"/api/turns/{s['turns'][-1]['id']}/toggle", json={}).json()["turns"][-1]["undone"] is True)

        # the record on disk is what a fresh process would read
        rec = pj.load(pid)
        check("record holds clips by index id and the log", len(rec.clips) == 2 and len(rec.turns) == len(turns))

        r = c.delete(f"/api/projects/{second}").json()
        check("deleted", all(p["id"] != second for p in r["projects"]) and r["open"] == pid)
        check("clips still on disk after delete", os.path.isfile(a) and os.path.isfile(b))

    print()
    print("ALL PASS" if not failures else f"FAILED: {', '.join(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
