"""AI Edit on the course key: does the chat only spend what the creator saw?

sarah (2026-10-18) asked for the chat to show when AI is on, running on her
course's OpenAI key ($25 for the whole team), each message showing what it
will cost before it's sent. No network: OpenAI's reply is played by a
stand-in, and every request it would have received is counted.

Who answers: nobody without a key; the key alone answers nothing; the key
with the AI switch on is OpenAI. The estimate is free and priced for whoever
answers. A message is answered only when it carries the cost the box showed;
then it is one undoable turn (the same ops as Claude's), the answer's cost is
on the turn, kept with the project and in the running total, and survives a
restart. A message about one shot carries that shot and its frame, and never
builds a new story. The app isn't held up while the AI thinks; Stop drops the
answer but counts its cost; an answer landing after another video was opened
changes neither. The app's own first story (from the brief) is built by the
free rules. A paid answer that failed still counts, saved at once. The
paused-moment chat follows the same rules and sends its frame at low detail.

    python tests/test_chat_ai.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Its own cache, always: the test flips the AI switch (ai.json), which must
# never be a real one. Empty keys, so web/.env on a dev Mac is never read.
if __name__ == "__main__":   # the indexer's worker processes re-run this file: they keep this cache
    os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-chat-ai-")
os.environ["VIBECUT_EXPORTS"] = os.path.join(os.environ["VIBECUT_CACHE"], "out")
os.environ.setdefault("VIBECUT_BED", "0")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException  # noqa: E402

from tests.test_board import CLIPS, PROPOSALS, session  # noqa: E402
from web.backend import app as A  # noqa: E402
from web.backend import llm, oai, timeline  # noqa: E402
from web.backend import projects as pj  # noqa: E402

oai.ENV_FILE = llm.ENV_FILE = Path(os.environ["VIBECUT_CACHE"]) / "no.env"

failures: list[str] = []
SHOT = "market000001:1"


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def op(**kw) -> dict:
    """One op as OpenAI's strict schema returns it: every field, unused ones null."""
    fields = llm.SCHEMA["properties"]["ops"]["items"]["required"]
    return {k: kw.get(k) for k in fields}


def answer(ops: list[dict], reply: str = "Cut the market shot.", finish: str = "stop") -> dict:
    return {"model": "gpt-6.1-sol", "usage": {"prompt_tokens": 6000, "completion_tokens": 900,
                                              "prompt_tokens_details": {"cached_tokens": 2000}},
            "choices": [{"finish_reason": finish, "message": {"content": json.dumps(
                {"reply": reply, "question": None, "choices": [], "direction": None, "ops": ops})}}]}


def refused(fn) -> HTTPException | None:
    try:
        fn()
    except HTTPException as e:
        return e
    return None


def main() -> int:
    s, cat = session()
    A.SESSION = s
    A.CATALOG["cat"] = cat
    A.CLIPS.clear()
    A.CLIPS.update({c["id"]: c for c in CLIPS})
    A._make_proposals = lambda d: PROPOSALS
    A._session = lambda: {}   # the fixture clips have no files to read sound from
    saved: list[int] = []
    A._save = lambda: saved.append(1)   # ...nor paths to save a project with
    A.WORKFLOW.state = "story"
    A.PROJECT["p"] = pj.Project(id="chat-ai", name="Chat")
    sent: list[dict] = []
    replies: list[dict] = []

    def stand_in(url, body, headers):
        sent.append(body)
        return replies.pop(0)
    real_post = oai._post
    oai._post = stand_in

    try:
        print("who answers")
        check("no key: nobody", llm.chat_provider() is None)
        os.environ["OPENAI_API_KEY"] = "sk-test"
        oai.switch(False)
        check("the key alone answers nothing", llm.chat_provider() is None)
        e = refused(lambda: A.api_chat(A.ChatReq(message="cut the market", ai_ok=0.05)))
        check("AI off: a typed edit is refused, says to turn AI on, sends nothing",
              e is not None and e.status_code == 409 and "turn AI on" in e.detail and not sent, e and e.detail)
        oai.switch(True)
        check("key + switch on: OpenAI", llm.chat_provider() == "openai")

        print("the cost, before anything is sent")
        est = A.api_chat_estimate()
        n = llm.prompt_chars(cat, s, A.PREFS.for_model()) + 300
        tin = n / llm.CHARS_PER_TOKEN
        want = [round((tin * 2.0 + o * 10.0) / 1e6, 4) for o in llm.OUT_TOKENS]
        check("priced at the course model's rates, as a range", est["on"] and est["provider"] == "openai"
              and est["usd"] == want and 0 < want[0] < want[1] < 0.1, json.dumps(est))
        check("reading it sent nothing", not sent)
        claude = None
        oai.switch(False)
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        claude = llm.estimate(n)
        os.environ["ANTHROPIC_API_KEY"] = ""
        oai.switch(True)
        check("Claude's price would be higher for the same message", claude["usd"][1] > est["usd"][1],
              f"{claude['usd']} vs {est['usd']}")

        print("a message")
        e = refused(lambda: A.api_chat(A.ChatReq(message="cut the market")))
        check("without the cost it was shown: refused, nothing sent",
              e is not None and e.status_code == 409 and not sent, e and e.detail)
        replies.append(answer([op(op="drop_shot", shot=SHOT)]))
        n_turns = len(s.turns)
        A.api_chat(A.ChatReq(message="cut the market", ai_ok=est["usd"][1]))
        body = sent[-1]
        check("one request", len(sent) == 1)
        check("the same instructions and a strict schema",
              body["messages"][0] == {"role": "system", "content": llm.SYSTEM}
              and body["response_format"]["json_schema"]["strict"]
              and body["response_format"]["json_schema"]["name"] == "storyboard_ops")
        check("the edit as text, then the creator's words", "STORYBOARD" in body["messages"][-1]["content"][-1]["text"]
              and body["messages"][-1]["content"][-1]["text"].endswith("USER: cut the market"))
        check("the conversation so far goes with it", any(m["role"] == "user" and m["content"] == "a day in Tokyo"
                                                         for m in body["messages"][1:-1]))
        t = A.SESSION.turns[-1]
        gone = SHOT not in [x["id"] for b in A.SESSION.board["beats"] for x in b["shots"]]
        check("one undoable turn that did it", len(A.SESSION.turns) == n_turns + 1 and t.kind == "chat" and gone)
        paid = oai.cost({"prompt_tokens": 6000, "completion_tokens": 900,
                         "prompt_tokens_details": {"cached_tokens": 2000}}, "gpt-6.1-sol")
        check("the answer's cost is on the turn", t.cost == round(paid, 4) and t.cost > 0, str(t.cost))
        ev = A.PROJECT["p"].events[-1]
        check("and kept with the project", ev["kind"] == "chat" and ev["cost"] == t.cost and ev["model"] == "gpt-6.1-sol")
        check("the running total", A._ai_spent() == t.cost and A.api_chat_estimate()["spent"] == t.cost)
        back = pj.turn_from_dict(json.loads(json.dumps(pj.turn_to_dict(t))))
        check("a restart keeps it", back.cost == t.cost)
        A.SESSION.toggle(t.id, cat, lambda d: PROPOSALS)
        check("Undo takes it back", SHOT in [x["id"] for b in A.SESSION.board["beats"] for x in b["shots"]])
        A.SESSION.toggle(t.id, cat, lambda d: PROPOSALS)

        print("about one shot")
        items = timeline.layout(A.SESSION.board)
        at = items[0]["seq_start"] + 0.3
        whole = A.api_chat_estimate()
        e_t = A.api_chat_estimate(t=at)
        check("priced with the shot and its frame, so a little higher", e_t["usd"][0] > whole["usd"][0]
              and e_t["per_char"] > 0 and e_t["base_chars"] == 300, f"{e_t['usd']} vs {whole['usd']}")
        replies.append(answer([op(op="choose_option", option="place"),
                               op(op="set_pace", beat=A.SESSION.board["beats"][0]["id"], direction="tighter",
                                  amount="a_little")], reply="Tightened."))
        real_image = A.moment.image
        A.moment.image = lambda m: "AAAA"      # the fixture clips have no index frames
        A.api_chat(A.ChatReq(message="too slow", ai_ok=e_t["usd"][1], t=at))
        A.moment.image = real_image
        text = sent[-1]["messages"][-1]["content"][-1]["text"]
        parts = sent[-1]["messages"][-1]["content"]
        check("the model is told which shot, and sees its frame", "PAUSED AT" in text
              and any(p_["type"] == "image_url" for p_ in parts))
        check("about this edit's moment: never a whole new story",
              not any(o["op"] == "choose_option" for o in A.SESSION.turns[-1].ops)
              and any(o["op"] == "set_pace" for o in A.SESSION.turns[-1].ops))
        A.SESSION.toggle(A.SESSION.turns[-1].id, cat, lambda d: PROPOSALS)

        print("while it thinks")
        import threading
        free: list[bool] = []

        def try_lock() -> None:
            got = A.LOCK.acquire(blocking=False)
            free.append(got)
            if got:
                A.LOCK.release()

        def thinking(url, body, headers):
            th = threading.Thread(target=try_lock)
            th.start()
            th.join()
            return stand_in(url, body, headers)
        oai._post = thinking
        replies.append(answer([op(op="drop_shot", shot=SHOT)]))
        A.api_chat(A.ChatReq(message="cut the market", ai_ok=whole["usd"][1]))
        check("the app isn't held up (no lock while the AI answers)", free == [True])
        A.SESSION.toggle(A.SESSION.turns[-1].id, cat, lambda d: PROPOSALS)

        def stopped(url, body, headers):
            A.api_chat_stop(A.StopReq(rid="box-1"))     # Stop pressed while it thinks
            return stand_in(url, body, headers)
        oai._post = stopped
        first = A.SESSION.board["beats"][0]["shots"][0]["id"]
        replies.append(answer([op(op="drop_shot", shot=first)]))
        n_turns, before = len(A.SESSION.turns), A._ai_spent()
        snap = json.dumps(A.SESSION.board, sort_keys=True, default=str)
        out = A.api_chat(A.ChatReq(message="cut the first shot", ai_ok=whole["usd"][1], rid="box-1"))
        check("Stop: the answer changes nothing", out.get("stopped") and len(A.SESSION.turns) == n_turns
              and json.dumps(A.SESSION.board, sort_keys=True, default=str) == snap)
        check("what it cost is still counted, and said", out["stop_cost"] and A._ai_spent() > before)
        check("and forgotten after", "box-1" not in A.STOPPED)

        other, _ = session()
        def elsewhere(url, body, headers):
            A.SESSION = other                           # another video opened meanwhile
            return stand_in(url, body, headers)
        oai._post = elsewhere
        replies.append(answer([op(op="drop_shot", shot=SHOT)]))
        n_turns, n_other = len(s.turns), len(other.turns)
        e = refused(lambda: A.api_chat(A.ChatReq(message="cut the market", ai_ok=whole["usd"][1])))
        check("another video opened meanwhile: neither is changed", e is not None and e.status_code == 409
              and len(s.turns) == n_turns and len(other.turns) == n_other, e and e.detail)
        A.SESSION = s
        oai._post = stand_in

        print("the first story, built by the app")
        from web.backend import board as bd
        A.SESSION = bd.Session()
        k = len(sent)
        A.api_chat(A.ChatReq(message="a day in Tokyo"))
        check("from the brief, with AI on: by the free rules, nothing sent", len(sent) == k
              and A.SESSION.turns and A.SESSION.turns[-1].cost is None, str(len(sent) - k))
        A.SESSION = s

        print("an answer that failed after it was paid for")
        replies.append(answer([], finish="length"))
        before = A._ai_spent()
        e = refused(lambda: A.api_chat(A.ChatReq(message="and the next", ai_ok=est["usd"][1])))
        check("says what went wrong", e is not None and e.status_code == 502 and "cut off" in e.detail, e and e.detail)
        check("and still counts what it cost", A._ai_spent() > before)
        check("saved there and then (a failed request isn't saved otherwise)", saved)

        print("the paused moment")
        items = timeline.layout(A.SESSION.board)
        at = items[0]["seq_start"] + 0.3
        info = A.api_moment(A.MomentReq(t=at))
        check("the box knows AI answers and what a message costs", info["llm"] and info["provider"] == "openai"
              and 0 < info["estimate"]["usd"][0] < info["estimate"]["usd"][1], json.dumps(info["estimate"]))
        k = len(sent)
        e = refused(lambda: A.api_moment_chat(A.MomentReq(t=at, message="too long")))
        check("without the cost it was shown: refused, nothing sent", e is not None and e.status_code == 409 and len(sent) == k)
        replies.append(answer([op(op="set_pace", beat=A.SESSION.board["beats"][0]["id"], direction="tighter",
                                  amount="a_little")], reply="Tightened it."))
        n_turns = len(A.SESSION.turns)
        out = A.api_moment_chat(A.MomentReq(t=at, message="too long", ai_ok=info["estimate"]["usd"][1]))
        check("answered with a proposal, nothing applied yet", out["ops"] and len(A.SESSION.turns) == n_turns)
        check("its cost comes back with it", out["cost"] and out["spent"] == A._ai_spent())

        print("the frame goes small")
        replies.append(answer([]))
        llm.interpret("hm", cat, A.SESSION, image_b64="AAAA")
        part = sent[-1]["messages"][-1]["content"][0]
        check("as a low-detail image", part["type"] == "image_url" and part["image_url"]["detail"] == "low")

        print("off again")
        oai.switch(False)
        k = len(sent)
        e = refused(lambda: A.api_chat(A.ChatReq(message="cut more", ai_ok=0.05)))
        check("nothing is sent, even with a cost", e is not None and e.status_code == 409 and len(sent) == k)
        e = refused(lambda: A.api_moment_chat(A.MomentReq(t=at, message="cut more", ai_ok=0.05)))
        check("the paused box too", e is not None and e.status_code == 409 and "AI" in e.detail and len(sent) == k)
        check("the estimate says nobody answers", not A.api_chat_estimate()["on"])
    finally:
        oai._post = real_post
        oai.switch(False)
        os.environ["OPENAI_API_KEY"] = ""

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
