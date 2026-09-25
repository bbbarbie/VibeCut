"""The rough cut: reject whole clips, trim the ones kept -- as a plan.

Runs cutgrammar.reject and cutgrammar.trim over the shoot and keeps the
result as decisions with reasons, never as edits to files. Every automatic
decision can be overridden by the person at the gate (or later), and every
override can be taken back: `auto` returns an item to what the machine
proposed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cutgrammar import reject, trim
from cutgrammar.signals import ClipSignals

from . import storyboard as sb

STEP_S = 2.0        # "longer" / "shorter" moves the target by this much
# Vision feature prints of the same view taken twice score ~0.9+; the
# numpy thumbnail fingerprint needs a stricter bar. Guesses, like the rest.
DUP_VISION = 0.93
DUP_THUMB = 0.97


@dataclass
class Plan:
    clips: dict[str, dict] = field(default_factory=dict)       # clip_id -> decision
    overrides: dict[str, str] = field(default_factory=dict)    # clip_id/shot_id -> action
    targets: dict[str, float] = field(default_factory=dict)    # shot_id -> target seconds (after longer/shorter)


def _embedding(rec: dict) -> tuple[np.ndarray, float]:
    embs = [np.asarray(s.get("embedding") or [], dtype=np.float32) for s in rec["shots"]]
    embs = [e for e in embs if e.size]
    if embs:
        return np.mean(embs, axis=0), DUP_VISION
    return np.asarray(rec["signals"]["thumb"], dtype=np.float32), DUP_THUMB


def compute(clips: dict[str, dict], old: Plan | None = None) -> Plan:
    plan = Plan(overrides=dict(old.overrides) if old else {}, targets=dict(old.targets) if old else {})
    recs = [c for c in clips.values() if c.get("signals")]
    cands, thresholds = [], []
    for r in recs:
        emb, thr = _embedding(r)
        faces = np.asarray(r.get("faces") or [], dtype=np.float64)
        cands.append(reject.Candidate(
            id=r["id"], name=r["name"], sig=ClipSignals.from_json(r["signals"]), embedding=emb,
            quality=float(np.mean([s["quality"] for s in r["shots"]])),
            when=sb.parse_when(r.get("capture_time")),
            faces=faces if faces.size else None))
        thresholds.append(thr)
    verdicts = reject.reject_all(cands, dup_threshold=min(thresholds) if thresholds else reject.DUP_SIMILARITY)

    for r, c in zip(recs, cands):
        v = verdicts[r["id"]]
        shots = {}
        for s in r["shots"]:
            sid = f"{r['id']}:{s['index']}"
            auto = trim.best_window(c.sig, None, c.faces, lo=s["start"], hi=s["end"])
            tgt = plan.targets.get(sid)
            w = trim.best_window(c.sig, tgt, c.faces, lo=s["start"], hi=s["end"]) if tgt else auto
            shots[sid] = {
                "id": sid, "full": [s["start"], s["end"]], "auto": [auto.start, auto.end],
                "window": [w.start, w.end], "target": w.target, "whole": w.whole,
                "reason_zh": w.reason_zh, "reason_en": w.reason_en, "notes": w.notes,
                "seconds": w.seconds[int(s["start"]):int(np.ceil(s["end"]))],
            }
        plan.clips[r["id"]] = {
            "id": r["id"], "name": r["name"], "duration": r["duration"],
            "auto_rejected": v.rejected, "code": v.code, "zh": v.zh, "en": v.en,
            "flags": v.flags, "talking": trim.is_talking(c.sig), "shots": shots,
            "evidence": v.evidence, "unverified": v.unverified() if v.rejected else [],
        }
    _apply_overrides(plan)
    return plan


def _apply_overrides(plan: Plan) -> None:
    for cid, c in plan.clips.items():
        o = plan.overrides.get(cid)
        c["override"] = o
        c["rejected"] = (c["auto_rejected"] and o != "keep") or o == "reject"
        for sid, s in c["shots"].items():
            so = plan.overrides.get(sid)
            s["override"] = so
            s["use"] = list(s["full"]) if so == "full" else list(s["window"])


def override(plan: Plan, target: str, action: str, clips: dict[str, dict]) -> Plan:
    """keep / reject a clip; full / auto / longer / shorter a shot. Recomputes."""
    if action == "auto":
        plan.overrides.pop(target, None)
        plan.targets.pop(target, None)
    elif action in ("keep", "reject"):
        plan.overrides[target] = action
    elif action == "full":
        plan.overrides[target] = "full"
    elif action in ("longer", "shorter"):
        cid = target.split(":")[0]
        shot = plan.clips[cid]["shots"][target]
        full = shot["full"][1] - shot["full"][0]
        cur = shot["window"][1] - shot["window"][0]
        plan.targets[target] = float(np.clip(cur + (STEP_S if action == "longer" else -STEP_S), 1, full))
        plan.overrides.pop(target, None)
    else:
        raise ValueError(f"unknown action {action!r}")
    return compute(clips, plan)


def mmss(s: float) -> str:
    return f"{int(s // 60)}:{int(round(s % 60)):02d}" if s % 60 < 59.5 else f"{int(s // 60) + 1}:00"


def summary(plan: Plan) -> dict:
    clips = list(plan.clips.values())
    kept = [c for c in clips if not c["rejected"]]
    raw = sum(c["duration"] for c in clips)
    cut = sum(s["use"][1] - s["use"][0] for c in kept for s in c["shots"].values())
    return {
        "clips": len(clips), "kept": len(kept), "rejected": len(clips) - len(kept),
        "raw": round(raw, 1), "cut": round(cut, 1), "ratio": round(cut / raw, 3) if raw else None,
        "line_zh": f"{len(clips)} 个片段 → 保留 {len(kept)} → 剪出 {mmss(cut)}（原始 {mmss(raw)}）",
        "line_en": f"{len(clips)} clips → {len(kept)} kept → {mmss(cut)} cut (from {mmss(raw)})",
    }


def for_story(plan: Plan | None) -> tuple[set[str], dict[str, tuple[float, float]]]:
    """(rejected clip ids, shot id -> (in, out)) for building storyboards."""
    if plan is None:
        return set(), {}
    rejected = {cid for cid, c in plan.clips.items() if c["rejected"]}
    windows = {sid: tuple(s["use"]) for c in plan.clips.values() for sid, s in c["shots"].items()}
    return rejected, windows
