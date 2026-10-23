"""Chat on pause: the message is about the paused moment, and nothing changes
until Apply.

The model is mocked: no key, no network, no cost. Checks that the moment the
model is told about is the one under the playhead (shot, clip time, words on
screen, neighbours), that pausing elsewhere tells it something else, that a
proposed edit is only previewed, that Apply is one undoable turn, and that
without a key nothing is sent and the box says why.

    python tests/test_moment.py
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-moment-")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException  # noqa: E402

from tests.test_board import CLIPS, PROPOSALS, session  # noqa: E402
from web.backend import app as A  # noqa: E402
from web.backend import llm, moment, timeline  # noqa: E402


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    s, cat = session()
    s.add({"kind": "direct", "text": "words", "ops": [
        {"op": "add_overlay", "kind": "caption", "text": "night market", "anchor": {"to": "shot", "id": "market000001:1"}, "at": 0.0}]},
        cat, lambda d: PROPOSALS)
    A.SESSION = s
    A.CATALOG["cat"] = cat
    A.CLIPS.clear()
    A.CLIPS.update({c["id"]: c for c in CLIPS})
    A._make_proposals = lambda d: PROPOSALS
    A._session = lambda: {}   # the fixture clips have no files to read sound from
    items = timeline.layout(s.board)
    mk = next(it for it in items if it["key"] == "market000001:1")
    t = mk["seq_start"] + 0.5

    print("the moment")
    m = moment.at(s.board, cat, A.CLIPS, A._overlays_public(s.board, cat, {})["items"], t)
    check("the shot under the playhead", m["key"] == "market000001:1" and m["clip"] == cat.shots["market000001:1"].clip_name, str(m["key"]))
    check("where in its clip", abs(m["src_t"] - (mk["src_start"] + 0.5)) < 0.01, str(m["src_t"]))
    check("its neighbours", m["before"] and m["after"] and m["before"]["key"] != m["key"])
    check("the words on screen", [w["text"] for w in m["words"]] == ["night market"], str(m["words"]))
    other = moment.at(s.board, cat, A.CLIPS, [], items[0]["seq_start"] + 0.2)
    check("paused elsewhere, a different moment", other["key"] != m["key"] and not other["words"])
    text = moment.describe(m)
    check("told to the model as text", "market000001:1" in text and "night market" in text and "PAUSED AT" in text)
    check("the header names shot, time and clip", moment.header(m).startswith(f"Shot {m['n']} · "))
    est = moment.estimate(20000, True)
    check("a cost estimate, a few cents", 0.01 < est["usd"][0] < est["usd"][1] < 0.2, str(est))

    print("no key")
    real_avail, real_interpret = llm.available, llm.interpret
    sent = []
    llm.interpret = lambda *a, **k: sent.append(1) or {}
    llm.available = lambda: False
    info = A.api_moment(A.MomentReq(t=t))
    check("the box knows there's no key, and still shows the moment", info["llm"] is False and info["header"].startswith("Shot"))
    try:
        A.api_moment_chat(A.MomentReq(t=t, message="cut this shorter"))
        refused = None
    except HTTPException as e:
        refused = e
    check("without a key nothing is sent, and it says why",
          refused is not None and refused.status_code == 409 and "AI" in refused.detail and not sent, str(refused and refused.detail))

    print("with a (mocked) key")
    llm.available = lambda: True
    seen = {}

    def fake(message, cat_, sess, rules="", moment="", image_b64=None, **kw):
        seen.update(message=message, moment=moment, image=image_b64)
        return {"reply": "Trimmed it to the busy part.", "question": None, "choices": [],
                "ops": [{"op": "drop_shot", "shot": "market000001:1"}]}
    llm.interpret = fake
    before = [[e["id"] for e in b["shots"]] for b in s.board["beats"]]
    n_turns = len(s.turns)
    out = A.api_moment_chat(A.MomentReq(t=t, message="this one drags", history=[{"who": "you", "text": "hm"}]))
    check("the model got the moment with the message", "market000001:1" in seen["moment"] and seen["message"] == "this one drags")
    check("and this box's earlier lines", "CREATOR: hm" in seen["moment"])
    check("a reply and a proposed edit", out["reply"] and out["ops"] == [{"op": "drop_shot", "shot": "market000001:1"}])
    check("the proposal is previewed as a diff", out["preview"] and out["preview"]["lines"], str(out["preview"]))
    check("nothing changed before Apply", len(s.turns) == n_turns
          and [[e["id"] for e in b["shots"]] for b in s.board["beats"]] == before)
    A.api_ops(A.OpsReq(ops=out["ops"], label="this one drags"))
    gone = "market000001:1" not in [e["id"] for b in A.SESSION.board["beats"] for e in b["shots"]]
    check("Apply makes it one turn", gone and len(A.SESSION.turns) == n_turns + 1)
    A.SESSION.toggle(A.SESSION.turns[-1].id, cat, lambda d: PROPOSALS)
    check("and one Undo takes it back", [[e["id"] for e in b["shots"]] for b in A.SESSION.board["beats"]] == before)
    llm.available, llm.interpret = real_avail, real_interpret

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_moment() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
