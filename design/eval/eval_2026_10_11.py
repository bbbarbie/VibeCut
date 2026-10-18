"""Eval of 2026-10-11: 20 real cases through the prototype, from the index.

Inputs are real: the creator's 42-clip shoot (from the index cache -- the
originals are in a folder this session can't read, so nothing that decodes
them runs here), her 4 reference reels, a downloaded vlog, and the 19 free
tracks on disk. Each case states its criterion before the result. Cases are
independent; a failure is reported, never retried with a different bar.

    python design/eval/eval_2026_10_11.py > design/eval/2026-10-11-eval.json
"""

from __future__ import annotations

import copy
import glob
import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np  # noqa: E402

from cutgrammar import grade, media, music as mu, style as st  # noqa: E402
from cutgrammar import calibrate as cal  # noqa: E402
from web.backend import bed, brief, cut, daylog, indexer, looks, pitch, reference, remix, seams, smooth, storyboard, tempo, timeline  # noqa: E402
from web.backend import board as bd  # noqa: E402

CACHE = Path(os.path.expanduser("~/.cache/vibecut"))
rows: list[dict] = []
ctx: dict = {}


def case(n: int, name: str, inp: str, criterion: str, fn) -> None:
    try:
        observed, ok = fn()
    except Exception as e:  # noqa: BLE001 -- a crash is a failed case, reported as such
        observed, ok = f"error: {type(e).__name__}: {str(e)[:140]}", False
        traceback.print_exc(file=sys.stderr)
    rows.append({"n": n, "case": name, "input": inp, "criterion": criterion, "observed": observed, "pass": bool(ok)})
    print(f"  {'PASS' if ok else 'FAIL'}  {n:2d} {name}: {observed}", file=sys.stderr)


def dur(b: dict) -> float:
    return sum(e["end"] - e["start"] for bt in b["beats"] for e in bt["shots"])


# 1 the shoot, from the cache
def c1():
    ids = os.listdir(CACHE / "clips")
    recs = [r for r in (indexer.load_indexed(c) for c in ids) if r and "sarah" in r["path"]]
    recs.sort(key=lambda r: r["capture_time"] or "")
    ctx["clips"] = {r["id"]: r for r in recs}
    full = sum(1 for r in recs if r["shots"] and "embedding" in r["shots"][0] and r.get("capture_time"))
    return f"{len(recs)} clips reloaded, {full} with shots + Vision embedding + capture time, " \
           f"{sum(r['duration'] for r in recs) / 60:.1f} min", len(recs) >= 40 and full == len(recs)


# 2 rough cut
def c2():
    plan = cut.compute(ctx["clips"], ask=False)
    ctx["plan"] = plan
    rejected = [c for c in plan.clips.values() if c["rejected"]]
    shaky_rejects = [c for c in rejected if c["code"] == "shaky"]
    summ = cut.summary(plan)
    kept = len(plan.clips) - len(rejected)
    return (f"{kept} of {len(plan.clips)} kept, {len(rejected)} thrown out ({', '.join(sorted({c['code'] for c in rejected}))}), "
            f"shaky rejections {len(shaky_rejects)}; {summ['line_en'][:70]}"), 0.5 <= kept / len(plan.clips) <= 1.0 and not shaky_rejects


# 3 tempo
def c3():
    feel = tempo.read(list(ctx["clips"].values()), cut.for_story(ctx["plan"]))
    ctx["pace"] = feel["pace"]
    return f"{feel['pace']} — {feel['why'][:90]}", feel["pace"] in tempo.NAMES and "clips" in feel["why"]


# 4 format
def c4():
    pool, _ = storyboard.usable(storyboard.shots_from_clips(list(ctx["clips"].values()), cut.for_story(ctx["plan"])))
    ctx["pool"] = pool
    up = sum(s.end - s.start for s in pool if ctx["clips"][s.clip_id]["height"] > ctx["clips"][s.clip_id]["width"])
    tot = sum(s.end - s.start for s in pool)
    share = up / tot
    fmt = brief.suggest_format(share, tot)
    ctx["usable_s"] = tot
    return f"upright share {share:.2f} of {tot:.0f} s usable → {fmt}", share == 1.0 and fmt in ("short", "tall") \
        and fmt == ("short" if tot <= 2 * brief.SHORT_MAX_S else "tall")


# 5 what the video is
def c5():
    about = pitch.guess(list(ctx["clips"].values()))
    ctx["about"] = about or "My video"
    return f"“{about}”", bool(about) and len(about) > 8


# 6 length marks
def c6():
    marks = brief.length_marks(ctx["usable_s"], ctx["about"])
    ctx["marks"] = marks
    secs = [m["seconds"] for m in marks["marks"]]
    short = brief.length_for("short", marks)
    return f"marks {secs}, suggested {marks['suggest']} ({marks['seconds']} s); short format → {short:.0f} s", \
        secs == sorted(secs) and short <= brief.SHORT_MAX_S and marks["why"]


# 7 three stories
def c7():
    style = {"seconds": brief.length_for("tall", ctx["marks"]), "captions": "describe", "pace": ctx["pace"],
             "format": "tall", "look": "cozy"}
    ctx["style"] = style
    ctx["make"] = lambda d: storyboard.build(list(ctx["clips"].values()), d.get("text", ""), vision=True,
                                             cut=cut.for_story(ctx["plan"]), style=d.get("style"))
    props = ctx["make"]({"text": ctx["about"], "style": style})
    ctx["props"] = props
    opts = props["options"]
    return f"{len(opts)} stories: " + "; ".join(f"{o['name']} ({len(o['beats'])} parts)" for o in opts) + f"; suggested {props.get('recommended')}", \
        len(opts) >= 2 and all(len(o["beats"]) >= 1 for o in opts)


# 8 choose the suggested story
def c8():
    cat = bd.Catalog.from_clips(list(ctx["clips"].values()))
    s = bd.Session()
    s.add({"kind": "chat", "text": ctx["about"], "ops": [], "direction": {"text": ctx["about"], "style": ctx["style"]}}, cat, ctx["make"])
    key = ctx["props"].get("recommended") or ctx["props"]["options"][0]["key"]
    t = s.add({"kind": "direct", "text": "choose", "ops": [{"op": "choose_option", "option": key}]}, cat, ctx["make"])
    ctx["s"], ctx["cat"] = s, cat
    b = s.board
    n = sum(len(bt["shots"]) for bt in b["beats"])
    missing = [e["id"] for bt in b["beats"] for e in bt["shots"] if e["id"] not in cat.shots]
    want = ctx["style"]["seconds"]
    return f"“{b['name']}”: {len(b['beats'])} parts, {n} shots, {dur(b):.0f} s (asked {want:.0f} s)", \
        not t.skipped and not missing and abs(dur(b) - want) <= 0.3 * want


# 9 no shot repeats another
def c9():
    s, cat = ctx["s"], ctx["cat"]
    ops, names = brief.repeat_ops(s.board, cat)
    if ops:
        s.add({"kind": "direct", "text": "repeats", "ops": ops}, cat, ctx["make"])
    again, _ = brief.repeat_ops(s.board, cat)
    return f"{len(ops)} look-alike shots taken out ({', '.join(names[:3])}{'…' if len(names) > 3 else ''}); second pass finds {len(again)}", not again


# 10 captions: the day, told
def c10():
    s, cat = ctx["s"], ctx["cat"]
    ops, notes = daylog.caption_ops(s.board, cat, ctx["about"], ask_model=False, places={})
    caps = [o for o in ops if o.get("kind") == "caption"]
    # (first run mis-parsed single-digit hours like "8:35 am" -- the eval's bug, not the product's; the criterion is unchanged)
    import re
    clocked = sum(1 for o in caps if re.match(r"\d{1,2}:\d\d (am|pm)", o["text"]))
    phrased = sum(1 for o in caps if " · " in o["text"])
    ctx["caption_ops"] = ops
    sample = "; ".join(o["text"] for o in caps[:3])
    return f"{len(caps)} captions, {clocked} start with the clock, {phrased} also say what's happening — e.g. {sample}", len(caps) >= 3 and clocked == len(caps)


# 11 every cut checked
def c11():
    s = ctx["s"]
    items = timeline.build(s.board, ctx["clips"], None)["items"]
    cuts = seams.check(items, ctx["clips"])
    ctx["cuts_before"] = cuts
    numeric = sum(1 for c in cuts if any(f.get("value") is not None for f in c["findings"]))
    rough = sum(1 for c in cuts if c["verdict"] != "ok")
    return f"{len(cuts)} cuts checked, {numeric} with numbers, {rough} rough", len(cuts) >= 5 and numeric == len(cuts)


# 12 smoother cuts
def c12():
    s, cat = ctx["s"], ctx["cat"]
    before = sum(1 for c in ctx["cuts_before"] if c["verdict"] != "ok")
    ops, said = smooth.propose(s.board, ctx["clips"], cat)
    if ops:
        s.add({"kind": "direct", "text": "Smoother cuts", "ops": ops}, cat, ctx["make"])
    after = sum(1 for c in seams.check(timeline.build(s.board, ctx["clips"], None)["items"], ctx["clips"]) if c["verdict"] != "ok")
    return f"{len(ops)} ops; rough cuts {before} → {after}; “{said[:70]}”", after <= before


# 13 length slider
def c13():
    s, cat = ctx["s"], ctx["cat"]
    target = 60.0
    ops, note = brief.length_ops(s.board, cat, ctx["pool"], target, True)
    if ops:
        s.add({"kind": "direct", "text": "length", "ops": ops}, cat, ctx["make"])
    got = dur(s.board)
    return f"{len(ops)} ops → {got:.0f} s for a 60 s target; “{note[:60]}”", abs(got - target) <= 0.2 * target


# 14 pace
def c14():
    s, cat = ctx["s"], ctx["cat"]
    _, windows = cut.for_story(ctx["plan"])
    talk = tempo.talking(list(ctx["clips"].values()), ctx["pool"])
    ops = tempo.pace_ops(s.board, cat, windows, "fast", talk)
    if ops:
        s.add({"kind": "direct", "text": "fast", "ops": ops}, cat, ctx["make"])
    cap = brief.PACE_CAP_S["fast"]
    longest = max((e["end"] - e["start"] for bt in s.board["beats"] for e in bt["shots"] if e["id"] not in talk), default=0)
    return f"{len(ops)} ops; longest non-talking shot {longest:.2f} s (cap {cap} s); {len(talk)} talking shots kept", longest <= cap + 0.05


# 15 the bed: a track
def c15():
    s, cat = ctx["s"], ctx["cat"]
    tracks = mu.LocalFolderSource(str(CACHE / "music" / "openverse" / "tracks")).list()
    fp = bed.fingerprint(s.board, cat, ctx["pace"])
    need = dur(s.board)
    mx = bed.pick(fp, tracks, need)
    ctx["mx"] = mx
    if mx is None:
        return f"{len(tracks)} tracks on disk, none picked for {need:.0f} s", False
    t = mx["track"]
    return f"{len(tracks)} tracks → “{t.title[:40]}” {mx['bpm']:.0f} BPM, in {mx['in']:.1f} s, drop {mx['drop']:.1f} s", \
        mx["in"] >= 0 and mx["in"] + need <= t.duration + 0.5


# 16 the bed: cuts on the beat, undone whole
def c16():
    s, cat = ctx["s"], ctx["cat"]
    before = [round(e["end"] - e["start"], 3) for bt in s.board["beats"] for e in bt["shots"]]
    ops, report = bed.ops(s.board, cat, ctx["mx"], set())
    t = s.add({"kind": "direct", "text": bed.__name__, "ops": ops}, cat, ctx["make"])
    on = report["on_beat"] / max(report["shots"], 1)
    s.toggle(t.id, cat, ctx["make"])
    restored = [round(e["end"] - e["start"], 3) for bt in s.board["beats"] for e in bt["shots"]] == before and s.board.get("music") is None
    s.toggle(t.id, cat, ctx["make"])
    return f"{report['on_beat']} of {report['shots']} cuts onto the beat ({on:.0%}); undo restores: {restored}", on >= 0.5 and restored and not t.skipped


# 17 the look grades the shoot
def c17():
    s, cat = ctx["s"], ctx["cat"]
    thumbs = reference._board_thumbs(s.board, cat)
    small = [x for x in (reference._read_jpeg(p, 48, 27) for p in thumbs[:24]) if x is not None]
    px = grade.pixels(np.stack(small))
    before = grade.stats(px)
    fit = looks.fit_grade(looks.get("cozy"), px)
    after = fit["numbers"]["after"]
    lifted = after["black"] >= min(18.0, before["black"]) - 0.5
    return f"{len(small)} thumbnails; warmth {before['warmth']:.1f} → {after['warmth']:.1f}, black {before['black']:.1f} → {after['black']:.1f}, sat {before['sat']:.3f} → {after['sat']:.3f}; {Path(fit['lut']).name}", \
        after["warmth"] >= before["warmth"] + 3 and lifted and os.path.isfile(fit["lut"])


# 18 a reference reel, learnt
def c18():
    rid = next(d for d in sorted(os.listdir(CACHE / "references")) if (CACHE / "references" / d / "source.mp4").exists())
    meta = json.loads((CACHE / "references" / rid / "meta.json").read_text())
    m = media.load(str(CACHE / "references" / rid / "source.mp4"))
    got = st.learn(m)
    pace, tr = got.get("pace") or {}, got.get("transitions") or {}
    ctx["ref_style"] = got
    return f"“{meta.get('title', '')[:40]}”: {pace.get('median_s')} s a shot, cuts {tr.get('share', {}).get('cut', 0):.0%}, {', '.join(tr.get('words', [])[:2])}", \
        pace.get("median_s") is not None and pace["median_s"] < 2.0 and abs(sum(tr.get("share", {}).values()) - 1) < 0.01


# 19 four reels become one fingerprint
def c19():
    styles = [json.loads((CACHE / "references" / d / "style.json").read_text()) for d in os.listdir(CACHE / "references")
              if (CACHE / "references" / d / "style.json").exists()]
    fp = remix.fingerprint(styles)
    ctx["fp"] = fp
    return f"{fp['refs']} refs → {remix.describe(fp)}", fp["refs"] >= 3 and 15 <= fp["duration"] <= 90 and fp["median_s"] < 2.0 and fp["bpm"][0] < fp["bpm"][1]


# 20 the remix picks the shoot's moments
def c20():
    plan = remix.plan_shots(ctx["clips"], ctx["fp"], cut=cut.for_story(ctx["plan"]))
    inside = all(p.shot.start - 1e-3 <= p.start < p.end <= p.shot.end + 1e-3 for p in plan.picks)
    clips_used = len({p.shot.clip_id for p in plan.picks})
    return f"{len(plan.picks)} moments from {clips_used} clips, {plan.duration:.1f} s, hook {len(plan.hook)} shot(s)", \
        len(plan.picks) >= 8 and inside and plan.hook and clips_used >= 0.6 * len(plan.picks)


# 21 (reserve) a downloaded vlog through the analyser
def c21():
    files = sorted(glob.glob(str(CACHE / "calibration" / "links" / "good" / "*.mp4")))
    r = cal.measure(files[0], "good", CACHE / "calibration" / "heads")
    return f"{r.name[:40]}: {r.n_shots} shots, {len(r.values)} findings ({', '.join(sorted(r.values))[:60]})", not r.error and len(r.values) >= 6


def main() -> int:
    case(1, "The shoot reloads from the index", "42 clips of the Sep 22 shoot, index cache only",
         "≥40 clips load, every one with shots, a Vision embedding and a capture time", c1)
    case(2, "Rough cut", "those clips", "50–100% kept; a shake reading only warns, never rejects", c2)
    case(3, "Tempo read from the footage", "those clips", "one of quick/steady/calm with a reason that names the clips", c3)
    case(4, "Frame suggested", "the usable shots", "all upright → a vertical frame, short or tall by how much there is", c4)
    case(5, "What the video is, from the clips", "those clips", "a description, no model", c5)
    case(6, "Length marks", "usable seconds + the description", "marks in order; the Short format ≤ 90 s; a reason", c6)
    case(7, "Three stories", "clips + style (tall, cozy, read pace)", "≥2 stories, each with parts", c7)
    case(8, "Choose the suggested story", "the stories", "a board whose shots all resolve, within 30% of the asked length", c8)
    case(9, "No shot repeats another", "the board", "after one pass, a second pass finds nothing", c9)
    case(10, "Describe captions", "the board + capture times + labels", "≥3 captions, every one starting with the clock", c10)
    case(11, "Every cut checked", "the board's cuts", "≥5 cuts, each with at least one numeric finding", c11)
    case(12, "Smoother cuts", "the board", "rough cuts do not increase", c12)
    case(13, "Length slider to 60 s", "the board", "lands within 20% of 60 s", c13)
    case(14, "Pace: fast", "the board", "no non-talking shot longer than the fast cap", c14)
    case(15, "The bed: a track picked", "the board + 19 free tracks on disk", "a track with in-point ≥ 0 that covers the edit", c15)
    case(16, "The bed: cuts on the beat", "the board + the track", "≥50% of cuts land on a beat; one undo restores everything", c16)
    case(17, "Cozy grades the shoot", "the board's thumbnails", "warmer by ≥3, blacks lifted to the floor, a .cube written", c17)
    case(18, "A reference reel learnt", "the creator's 50 s reference reel", "median shot < 2 s; transition shares sum to 1", c18)
    case(19, "Four reels → one fingerprint", "the 4 references' style records", "15–90 s, median shot < 2 s, a tempo range", c19)
    case(20, "Remix picks the moments", "the shoot + the fingerprint", "≥8 moments inside their shots, a hook, spread over clips", c20)
    case(21, "A downloaded vlog measured", "one of the 14 fetched vlogs", "≥6 findings with numbers (reserve case)", c21)
    print(json.dumps(rows, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
