"""What the creator's edits teach, and only what they say they should.

Adapted from the preference state machine in montage-vlog-compiler (MIT;
see NOTICE). The rule it exists for: an edit is not a taste. Cutting the
market because this market footage is weak says nothing about markets.
If every change were learned, the tool would drift towards whatever the
last shoot happened to need, and the creator couldn't tell why.

So each edit turn becomes a *candidate*: what changed (the computed diff,
never the model's account of it), and what the creator said. It stays a
candidate until the creator sorts it, and only two sortings produce a rule
anyone reuses:

    long_term       every future video -- needs the rule, where it applies,
                    and where it doesn't, in their words
    project         this video only -- gone when the shelf is cleared
    single_edit     this spot, this once -- nothing learned
    compliance_fix  privacy, rights, platform rules -- never taste
    rejected        don't learn from this

Silence is never confirmation, the system can't confirm, and a candidate
whose turn was undone can't be confirmed: its before/after no longer
exists to be read back. Rules are never silently overwritten -- revoking
or narrowing one keeps it, marked, with who did it and when.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import board as bd

SCHEMA = "vibecut-preferences/1"
CLASSES = ("long_term", "project", "single_edit", "compliance_fix", "rejected")
LEARNED = ("long_term", "project")

# The creator saying it should stick. Only ever a *suggestion* for how to
# sort the candidate; the sorting itself is still theirs.
KEEP = ("以后也这样", "以后都这样", "以后也", "以后都", "下次也", "每次都",
        "from now on", "always do this", "always do that", "every time", "every video",
        "remember this", "remember that")


class PreferenceError(Exception):
    pass


def says_keep(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in KEEP)


def _edit_turns(session: bd.Session) -> list[bd.Turn]:
    """Turns that changed the storyboard by hand or by chat. Picking a
    proposal is a choice of starting point, not an edit."""
    out = []
    for t in session.turns:
        if not t.ops or all(o.get("op") == "choose_option" for o in t.ops):
            continue
        out.append(t)
    return out


def _readable(t: bd.Turn) -> bool:
    return not t.undone and bool(t.lines) and any(l["kind"] not in ("none",) for l in t.lines)


class Preferences:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.rules: list[dict] = self._load()      # long-term, including retired ones
        self.project: list[dict] = []              # this video only
        self.decisions: dict[int, dict] = {}       # turn id -> how it was sorted

    # ---- storage ---------------------------------------------------------

    def _load(self) -> list[dict]:
        if not self.path:
            return []
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return []
        return data.get("rules", []) if data.get("schema") == SCHEMA else []

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"schema": SCHEMA, "rules": self.rules}, indent=2, ensure_ascii=False))
        tmp.replace(self.path)
        from . import cloud
        cloud.push_rules(self.rules)

    def absorb(self, rows: list[dict]) -> int:
        """Rules from the mirror: new ids are added, known ids take the newer
        copy. Returns how many changed. Saved without pushing back."""
        changed = 0
        by_id = {str(r.get("id")): i for i, r in enumerate(self.rules) if r.get("id")}
        for row in rows:
            rule = row.get("value")
            if not isinstance(rule, dict) or not rule.get("id"):
                continue
            i = by_id.get(str(rule["id"]))
            if i is None:
                self.rules.append(rule)
                changed += 1
            elif (rule.get("updated") or rule.get("created") or 0) > (self.rules[i].get("updated") or self.rules[i].get("created") or 0):
                self.rules[i] = rule
                changed += 1
        if changed and self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"schema": SCHEMA, "rules": self.rules}, indent=2, ensure_ascii=False))
        return changed

    def new_project(self) -> None:
        """The shelf was cleared: this video's rules and sortings go with it."""
        self.project, self.decisions = [], {}

    # ---- candidates ------------------------------------------------------

    def candidates(self, session: bd.Session) -> list[dict]:
        edits = _edit_turns(session)
        keep_after: set[int] = set()
        # "以后也这样" on its own refers to the edit just before it.
        prev = None
        for t in session.turns:
            if t in edits:
                prev = t.id
            elif t.kind == "chat" and says_keep(t.text) and prev is not None:
                keep_after.add(prev)
        out = []
        for t in edits:
            d = self.decisions.get(t.id)
            out.append({
                "turn": t.id, "said": t.text, "kind": t.kind,
                "lines": [l["text"] for l in t.lines if l["kind"] != "none"],
                "suggested": "long_term" if (says_keep(t.text) or t.id in keep_after) else "single_edit",
                "readable": _readable(t),
                "status": "candidate" if d is None else ("rejected" if d["klass"] == "rejected" else "confirmed"),
                "klass": d["klass"] if d else None,
                "rule": d.get("rule_id") if d else None,
            })
        return out

    # ---- sorting ---------------------------------------------------------

    def classify(self, session: bd.Session, turn_id: int, klass: str, actor: str,
                 rule: str = "", scope: str = "", counter: str = "", reason: str = "") -> dict:
        if actor != "user":
            raise PreferenceError("only the creator can decide what's learned")
        if klass not in CLASSES:
            raise PreferenceError(f"unknown kind {klass!r}")
        turn = next((t for t in _edit_turns(session) if t.id == turn_id), None)
        if turn is None:
            raise PreferenceError("that turn didn't change the storyboard")
        if not _readable(turn):
            raise PreferenceError("that edit was undone — there's no before and after left to learn from")
        old = self.decisions.get(turn_id)
        if old and old.get("rule_id") and self._find(old["rule_id"]).get("active"):
            raise PreferenceError("already remembered — forget or narrow that rule first")

        rule, scope, counter, reason = (x.strip() for x in (rule, scope, counter, reason))
        if klass in LEARNED and not rule:
            raise PreferenceError("say the rule in your own words")
        if klass == "long_term" and not (scope and counter):
            raise PreferenceError("for every video, say when it applies and when it doesn't")

        now = time.time()
        decision = {"turn": turn_id, "klass": klass, "at": now}
        if klass in LEARNED:
            rec = {
                "id": f"r{int(now * 1000):x}{turn_id}", "klass": klass, "rule": rule,
                "scope": scope, "counter": counter, "reason": reason, "active": True,
                # the before/after, as computed from the boards -- readable later
                "evidence": {"said": turn.text, "changed": [l["text"] for l in turn.lines]},
                "history": [{"at": now, "action": "confirmed", "klass": klass, "actor": actor}],
            }
            if klass == "long_term":
                self.rules.append(rec)
                self._save()
            else:
                self.project.append(rec)
            decision["rule_id"] = rec["id"]
        self.decisions[turn_id] = decision
        return decision

    def _find(self, rid: str) -> dict:
        for r in self.rules + self.project:
            if r["id"] == rid:
                return r
        raise PreferenceError(f"no rule {rid}")

    def revoke(self, rid: str, actor: str) -> None:
        r = self._find(rid)
        if not r["active"]:
            return
        r["active"] = False
        r["history"].append({"at": time.time(), "action": "revoked", "klass": r["klass"], "actor": actor})
        if r in self.rules:
            self._save()

    def narrow(self, rid: str, actor: str) -> None:
        """Every video -> this video only. The long-term record stays, retired."""
        r = self._find(rid)
        if r["klass"] != "long_term" or not r["active"]:
            raise PreferenceError("only an active every-video rule can be narrowed")
        now = time.time()
        r["active"] = False
        r["history"].append({"at": now, "action": "narrowed", "klass": "project", "actor": actor})
        self._save()
        p = {**r, "id": r["id"] + "p", "klass": "project", "active": True,
             "history": [*r["history"], {"at": now, "action": "confirmed", "klass": "project", "actor": actor}]}
        self.project.append(p)
        for d in self.decisions.values():
            if d.get("rule_id") == rid:
                d.update(klass="project", rule_id=p["id"])

    # ---- use -------------------------------------------------------------

    def active(self) -> list[dict]:
        return [r for r in self.rules + self.project if r["active"]]

    def for_model(self) -> str:
        """Confirmed rules only. A candidate is never shown to the model."""
        rs = self.active()
        if not rs:
            return ""
        out = ["CREATOR RULES (the creator confirmed these; follow them when they apply, "
               "unless this message says otherwise):"]
        for r in rs:
            where = "every video" if r["klass"] == "long_term" else "this video"
            extra = "".join(f"; {k}: {r[v]}" for k, v in (("applies", "scope"), ("not when", "counter")) if r[v])
            out.append(f"- {r['rule']} ({where}{extra})")
        return "\n".join(out)

    def public(self, session: bd.Session) -> dict:
        return {"candidates": self.candidates(session),
                "rules": [{k: r[k] for k in ("id", "klass", "rule", "scope", "counter", "reason",
                                             "active", "evidence", "history")}
                          for r in self.rules + self.project]}
