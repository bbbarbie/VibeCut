"""Make the cuts smoother: one turn, asked for, undoable. Never by default.

Two moves an editor makes once the story is set, both proposed as ordinary
ops (move_shot, trim) so the diff is computed and Undo takes them back:

1. **Order within a part** (research 08 P3-2). Inside one part, shots can
   often be swapped without changing what the part says -- and one order
   cuts smoothly (light to light, busy to busy, wide to close) while
   another jolts at every join. A small beam search looks for the order
   with the least total roughness (cutgrammar.joins.cost), plus a penalty
   for every pair it puts out of filming order (TIME_WEIGHT), so the day
   still runs forward unless a swap clearly pays for itself. The cuts into
   and out of the part are counted too. Parts never change places.
   (FilmGPT's footage-constrained next-shot idea, with hand-made scores
   instead of a model.)

2. **Cut on the action** (P3-1). A shot's window moves up to MAX_SHIFT_S
   inside its own shot, toward seconds where the picture is moving at
   both ends -- a cut hidden inside a movement is the cheapest craft there
   is -- but never onto a word, and never to a worse-made second.

Both are [prior]: the weights are guesses and the signals are one sample a
second, so "the action" is a busy second, not a frame. That's why this is
a button the creator presses and judges, not something the edit does to
itself (CLAUDE.md: no fixer before calibration).
"""

from __future__ import annotations

import itertools

from cutgrammar import joins

from . import board as bd
from . import seams

TIME_WEIGHT = 0.35    # roughness a reorder must save per pair it puts out of filming order
BEAM = 12
MAX_PART = 12         # longer parts keep their order (the search would be guesswork)
MAX_SHIFT_S = 2.0
SHIFT_STEP_S = 1.0    # the index's resolution
MIN_GAIN = 1.3        # a nudge must make the edges this much busier...
MIN_MOTION = 3.0      # ...and actually reach movement
MAX_QUALITY_LOSS = 0.1
SPEECH_EDGE = 0.3     # a second this voiced is a word: don't cut there


def _items(board: dict) -> list[dict]:
    from . import timeline as tlm
    return tlm.layout(board)


def _pair_cost(sides: dict, a: str | None, b: str | None, cache: dict) -> float:
    if a is None or b is None or sides.get(a) is None or sides.get(b) is None:
        return 0.0
    if (a, b) not in cache:
        fs = joins.measure(sides[a], sides[b])
        joins.gate(fs, {"meta", "still", "audio"})
        cache[(a, b)] = joins.cost(fs)
    return cache[(a, b)]


def _inversions(order: list[str], rank: dict[str, int]) -> int:
    return sum(1 for x, y in itertools.combinations(order, 2) if rank[x] > rank[y])


def best_order(keys: list[str], rank: dict[str, int], sides: dict, before: str | None, after: str | None,
               cache: dict) -> tuple[list[str], float, float]:
    """(order, its cost, the current order's cost) for one part."""
    def total(order: list[str]) -> float:
        c = _pair_cost(sides, before, order[0], cache) + _pair_cost(sides, order[-1], after, cache)
        c += sum(_pair_cost(sides, x, y, cache) for x, y in zip(order, order[1:]))
        return c + TIME_WEIGHT * _inversions(order, rank)

    now = total(keys)
    if len(keys) < 2 or len(keys) > MAX_PART:
        return keys, now, now
    beam: list[tuple[float, list[str]]] = [(0.0, [])]
    for _ in keys:
        grown = []
        for c, seq in beam:
            last = seq[-1] if seq else before
            for k in keys:
                if k in seq:
                    continue
                step = _pair_cost(sides, last, k, cache) + TIME_WEIGHT * sum(1 for x in seq if rank[x] > rank[k])
                grown.append((c + step, seq + [k]))
        grown.sort(key=lambda t: t[0])
        beam = grown[:BEAM]
    best = min(beam, key=lambda t: t[0] + _pair_cost(sides, t[1][-1], after, cache))[1]
    return best, total(best), now


def order_ops(board: dict, clips: dict) -> tuple[list[dict], dict]:
    """move_shot ops that reorder shots within parts, and a summary."""
    items = _items(board)
    sides = {it["key"]: seams.side(it, clips) for it in items}
    order = [it["key"] for it in items]
    cache: dict = {}
    ops, saved, parts = [], 0.0, 0
    for bi, beat in enumerate(board["beats"]):
        keys = [bd.key(s) for s in beat["shots"]]
        if any(bd.is_gap(s) for s in beat["shots"]):
            continue    # a gap is a deliberate hole (a voiceover line); leave the part as placed
        first = order.index(keys[0])
        before = order[first - 1] if first > 0 else None
        after = order[first + len(keys)] if first + len(keys) < len(order) else None
        # filming order of this part's shots, by the clip's capture time then source time
        when = {k: (sides[k].when.timestamp() if sides[k] and sides[k].when else float(i))
                for i, k in enumerate(keys)}
        rank = {k: i for i, k in enumerate(sorted(keys, key=lambda k: when[k]))}
        new, c_new, c_now = best_order(keys, rank, sides, before, after, cache)
        if new != keys and c_new < c_now - 0.05:
            parts += 1
            saved += c_now - c_new
            ops += [{"op": "move_shot", "shot": k, "beat": beat["id"], "to_index": i} for i, k in enumerate(new)]
    return ops, {"parts": parts, "saved": round(saved, 2)}


def _mean(x: list[float], a: float, b: float) -> float:
    i, j = max(0, int(a)), min(len(x), max(int(a) + 1, int(-(-b // 1))))
    return sum(x[i:j]) / max(1, j - i) if x[i:j] else 0.0


def nudge_ops(board: dict, clips: dict, cat: bd.Catalog) -> tuple[list[dict], dict]:
    """trim ops that slide shot windows onto movement, within their own shot."""
    ops, moved = [], 0
    for beat in board["beats"]:
        for e in beat["shots"]:
            if bd.is_gap(e) or e["id"] not in cat.shots:
                continue
            c = clips.get(e["id"].split(":")[0]) or {}
            sig = c.get("signals") or {}
            mot, q, sp = sig.get("motion") or [], sig.get("quality") or [], sig.get("speech") or []
            if not mot:
                continue
            src = cat.shots[e["id"]]
            a0, b0 = e["start"], e["end"]
            length = b0 - a0

            def edges(a: float) -> float:
                return (_mean(mot, a, a + 1) + _mean(mot, a + length - 1, a + length)) / 2

            def ok(a: float) -> bool:
                z = a + length
                return (src.start - 1e-6 <= a and z <= src.end + 1e-6
                        and _mean(sp, a, a + 1) < SPEECH_EDGE and _mean(sp, z - 1, z) < SPEECH_EDGE
                        and _mean(q, a, z) >= (1 - MAX_QUALITY_LOSS) * _mean(q, a0, b0))
            now = edges(a0)
            best, best_v = a0, now
            k = SHIFT_STEP_S
            while k <= MAX_SHIFT_S + 1e-9:
                for a in (a0 - k, a0 + k):
                    if ok(a) and edges(a) > best_v:
                        best, best_v = a, edges(a)
                k += SHIFT_STEP_S
            if best != a0 and best_v >= MIN_MOTION and best_v >= MIN_GAIN * max(now, 1e-6):
                key, z = bd.key(e), round(best + length, 3)
                # extend first on the side it moves to, so the shot never collapses
                if best > a0:
                    ops += [{"op": "trim", "shot": key, "edge": "out", "to": z},
                            {"op": "trim", "shot": key, "edge": "in", "to": round(best, 3)}]
                else:
                    ops += [{"op": "trim", "shot": key, "edge": "in", "to": round(best, 3)},
                            {"op": "trim", "shot": key, "edge": "out", "to": z}]
                moved += 1
    return ops, {"shots": moved}


def propose(board: dict, clips: dict, cat: bd.Catalog, order: bool = True, nudge: bool = True) -> tuple[list[dict], str]:
    """The ops for one 'smoother cuts' turn, and a sentence saying what they do."""
    ops, said = [], []
    if order:
        o, s = order_ops(board, clips)
        ops += o
        if s["parts"]:
            said.append(f"reordered shots in {s['parts']} part{'s' * (s['parts'] != 1)} so the cuts flow")
    if nudge:
        n, s = nudge_ops(board, clips, cat)
        ops += n
        if s["shots"]:
            said.append(f"moved {s['shots']} cut{'s' * (s['shots'] != 1)} onto movement")
    if not said:
        return [], "Nothing to smooth: no reorder or nudge made the cuts clearly smoother."
    text = "; ".join(said)
    return ops, text[0].upper() + text[1:] + ". Undo if it doesn't feel right — these are first guesses."
