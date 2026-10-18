"""The launch log counts what the checklist asks for, from the records alone.

Through the API: a project exported from the default path is a completion;
its "would you post this?" answer makes it a success or a not-postable
failure with the creator's words; a project with clips but no export is
neither; the bed's outcome is an event. All of it survives a reopen.

    python tests/test_launchlog.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-launchlog-"))
os.environ.setdefault("VIBECUT_EXPORTS", os.path.join(os.environ["VIBECUT_CACHE"], "out"))
os.environ.setdefault("VIBECUT_BED", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def main() -> int:
    from fastapi.testclient import TestClient
    from tests.test_projects import TMP as PTMP, clip, wait
    from web.backend import app as backend
    from web.backend import launchlog
    a = clip(PTMP / "ll-a.mp4", 6, "0xff8a1e", "0x2a3440", "'325+40*sin(t)'", "2026-09-20T08:10:00")
    b = clip(PTMP / "ll-b.mp4", 7, "0x1ec8ff", "0x203028", "'120+30*t'", "2026-09-20T11:05:00")
    with TestClient(backend.app) as c:
        r = c.post("/api/projects", json={"name": "Launch"}).json()
        pid = r["project"]["id"]
        wait(c, c.post("/api/import", json={"paths": [a, b, str(PTMP / "nope.mp4")]}).json())
        c.post("/api/brief/auto", json={"format": "short", "look": "clean"})
        c.post("/api/cut/approve", json={})
        s = c.get("/api/session").json()
        s = c.post("/api/chat", json={"message": s["brief"]["message"], "style": s["brief"]["style"]}).json()
        s = c.post("/api/ops", json={"ops": [{"op": "choose_option", "option": s["proposals"]["options"][0]["key"]}], "label": "pick"}).json()
        job = c.post("/api/export", json={"music": False}).json()
        job = c.post(f"/api/export/{job['id']}/start", json={"schedule": []}).json()
        for _ in range(600):
            if job["stage"] in ("done", "error"):
                break
            time.sleep(0.25)
            job = c.get(f"/api/export/{job['id']}").json()
        check("exported", job["stage"] == "done", job.get("error") or "")
        s = c.get("/api/session").json()
        e = s["exports"][-1]
        check("the export record says how it was made", e["default_path"] is True and e["chat_turns"] == 0 and e["elapsed"] > 0, json.dumps(e)[:160])
        s = c.post("/api/exports/0/verdict", json={"post": False, "note": "too many kitchen shots"}).json()
        check("the verdict is on the record, with the words", s["exports"][0]["verdict"]["post"] is False
              and s["exports"][0]["verdict"]["note"] == "too many kitchen shots")
        check("a bad index is refused", c.post("/api/exports/9/verdict", json={"post": True}).status_code == 404)
        # a second project with clips and no export
        c.post("/api/projects", json={"name": "Half"})
        wait(c, c.post("/api/import", json={"paths": [a]}).json())
        backend._close_project()
        # back from disk
        s = c.post(f"/api/projects/{pid}/open", json={}).json()["session"]
        check("the verdict survives a reopen", s["exports"][0]["verdict"]["note"] == "too many kitchen shots")
        backend._close_project()
    summ = launchlog.summary()
    check("two projects, one completion, none successful, one judged",
          summ["projects"] == 2 and summ["completions"] == 1 and summ["successes"] == 0 and summ["judged"] == 1, json.dumps({k: summ[k] for k in ("projects", "completions", "successes", "judged")}))
    check("the failure is counted, and the unreadable file", summ["failures"]["not_postable"] == 1 and summ["failures"]["unreadable_files"] == 1, json.dumps(summ["failures"]))
    check("the feedback carries the creator's words", any("kitchen" in f["note"] for f in summ["feedback"]))
    check("costs: no model calls, some render time", summ["costs"]["model_calls"] == 0 and summ["costs"]["render_seconds"] > 0, json.dumps(summ["costs"]))
    page = launchlog.page(summ)
    check("the page reads", "completions (exported from the default path) 1" in page and "kitchen" in page)
    # an older record without events still counts
    old = [{"name": "old", "clips": {"x": "/x.mp4"}, "exports": [{"job": "j", "elapsed": 3}], "turns": []}]
    s2 = launchlog.summary(old)
    check("a record from before events existed still counts as a completion", s2["completions"] == 1 and s2["successes"] == 0)

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
