"""Three storyboards from one shoot, by axis enumeration. No language model.

Each axis is a different grouping key over the index -- when it was
filmed, where, and what is in frame. Because the keys differ structurally,
the three edits differ structurally; diversity is guaranteed rather than
hoped for, and every choice can be explained. v1 deliberately stops here:
it is the cheapest way to find out whether offering several edits is worth
anything to a creator before any model is put behind it.

The direction line is read by keyword matching against the on-device image
labels, and nothing more. The reply says exactly which words were used.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

# Shots Vision calls screenshots/documents, and shots that are mostly unusable.
# The quality floor is a guess, like every threshold in cutgrammar; it only
# decides what is left off the storyboard, never what is cut out of a file.
MIN_QUALITY = 0.25
# Evening and night shots score low on exposure by nature. One with lights in
# it -- lit windows, street lamps, a campus at night -- is the end of the day,
# not a mistake: it is never left out for quality alone. [prior]
NIGHT_FROM, NIGHT_TO = 18, 6
LIT = 0.4
SESSION_GAP = timedelta(minutes=45)
PLACE_RADII_M = [120, 300, 700, 1500, 4000, 15000, 60000]
MAX_BEATS = 6

# Direction words -> Vision label identifiers that count as a match.
THEMES = {
    "food": {"food", "meal", "dish", "dessert", "baked_goods", "bread", "sushi", "noodle",
             "ramen", "pasta", "pizza", "fruit", "vegetable", "meat", "seafood", "cake",
             "restaurant", "cafe", "drink", "coffee", "tea", "beverage", "cocktail",
             "wine", "beer", "sandwich", "burger", "salad", "soup", "rice", "breakfast",
             "dining_room", "table", "tableware", "kitchen", "cooking", "sweets", "ice_cream"},
    "people": {"people", "adult", "child", "teen", "baby", "portrait", "crowd", "selfie"},
    "nature": {"plant", "tree", "flower", "mountain", "forest", "grass", "sky", "water",
               "lake", "river", "garden", "outdoor", "landscape", "hill", "waterfall"},
    "sea": {"water", "beach", "ocean", "sea", "shore", "sand", "wave", "boat", "coast"},
    "city": {"structure", "building", "street", "road", "city", "skyscraper", "car",
             "vehicle", "bridge", "sign", "urban", "train", "shop", "storefront"},
    "night": {"night", "light", "illumination", "neon", "fireworks", "dark", "lamp", "candle"},
    "temple": {"temple", "shrine", "church", "religious", "place_of_worship", "pagoda",
               "monument", "architecture", "statue"},
    "animal": {"animal", "dog", "cat", "bird", "fish", "pet", "mammal"},
    "music": {"performance", "concert", "musical_instrument", "music", "stage", "guitar"},
    "dance": {"dance", "dancing", "performance", "stage", "recreation"},
}
ALIASES = {
    "eat": "food", "eating": "food", "foods": "food", "meals": "food", "dinner": "food",
    "lunch": "food", "breakfast": "food", "restaurants": "food", "cafes": "food",
    "friends": "people", "family": "people", "faces": "people", "me": "people",
    "beach": "sea", "ocean": "sea", "streets": "city", "street": "city", "urban": "city",
    "nightlife": "night", "evening": "night", "temples": "temple", "shrines": "temple",
    "shrine": "temple", "animals": "animal", "dogs": "animal", "cats": "animal",
    "concert": "music", "show": "music", "outdoors": "nature", "hiking": "nature",
    "mountains": "nature", "dancing": "dance",
}
PRETTY = {
    "people": "people", "adult": "people", "structure": "buildings",
    "outdoor": "outdoors", "document": "screens", "screenshot": "screens",
    "optical_equipment": "glasses", "eyeglasses": "glasses", "recreation": "leisure",
}


@dataclass
class Shot:
    id: str
    clip_id: str
    clip_name: str
    index: int
    start: float
    end: float
    thumb: str
    quality: float
    aesthetic: float | None
    utility: bool
    when: datetime | None
    gps: tuple[float, float] | None
    labels: dict[str, float]
    faces: int
    face_area: float
    activity: float
    vec: np.ndarray
    order: int = 0          # position in plain file order
    lean: bool = False
    contrast: float = 0.0   # best frame's contrast part (bestframe), lights against the dark

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def score(self) -> float:
        """Craft score for ranking; Apple's aesthetics folded in when present."""
        if self.aesthetic is None:
            return self.quality
        return 0.5 * self.quality + 0.5 * (self.aesthetic + 1) / 2


@dataclass
class Beat:
    title: str
    detail: str
    shots: list[Shot]
    lean: bool = False


@dataclass
class Option:
    key: str
    name: str
    axis: str
    summary: str
    beats: list[Beat]
    notes: list[str] = field(default_factory=list)
    degraded: bool = False


# --------------------------------------------------------------------------
# index -> shots
# --------------------------------------------------------------------------

def parse_when(s: str | None) -> datetime | None:
    """ISO-ish capture time. Keeps the camera's own clock, zone dropped.

    Apple's '2026-08-02T14:40:20-0400' is already local; a bare UTC
    'creation_time' is converted to this machine's zone as the best guess.
    """
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    s = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", s)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is not None and dt.utcoffset() == timedelta(0):
        dt = dt.astimezone()  # UTC stamp -> local guess
    return dt.replace(tzinfo=None)


def shots_from_clips(clips: list[dict], cut: tuple[set, dict] | None = None) -> list[Shot]:
    """Shots as storyboard material. With `cut` (rejected clip ids, shot id ->
    (in, out)) from the approved rough cut, rejected clips are left out and
    every kept shot is only its trimmed window."""
    rejected, windows = cut if cut else (set(), {})
    out: list[Shot] = []
    for c in sorted(clips, key=lambda c: (parse_when(c.get("capture_time")) or datetime.max, c["name"])):
        if c["id"] in rejected:
            continue
        base = parse_when(c.get("capture_time"))
        for s in c["shots"]:
            a, b = windows.get(f"{c['id']}:{s['index']}", (s["start"], s["end"]))
            emb = np.asarray(s.get("embedding") or [], dtype=np.float32)
            if emb.size == 0:
                emb = np.sqrt(np.asarray(s.get("hist") or [0.0], dtype=np.float32))
            emb = emb / (np.linalg.norm(emb) + 1e-9)
            out.append(Shot(
                id=f"{c['id']}:{s['index']}",
                clip_id=c["id"],
                clip_name=c["name"],
                index=s["index"],
                start=a,
                end=b,
                thumb=f"/api/thumbs/{c['id']}/{s['thumb']}",
                quality=s["quality"],
                aesthetic=s.get("aesthetic"),
                utility=bool(s.get("utility")),
                when=base + timedelta(seconds=a) if base else None,
                gps=tuple(c["gps"]) if c.get("gps") else None,
                labels={k: v for k, v in s.get("labels", [])},
                faces=s.get("faces", 0),
                face_area=s.get("face_area", 0.0),
                activity=s.get("activity", 0.0),
                vec=emb,
                contrast=float((s.get("parts") or {}).get("contrast", 0.0)),
            ))
    for i, s in enumerate(out):
        s.order = i
    return out


def lit_night(s: Shot) -> bool:
    night = s.when is not None and (s.when.hour >= NIGHT_FROM or s.when.hour < NIGHT_TO)
    night = night or any(s.labels.get(k, 0) >= 0.3 for k in ("night", "illumination", "evening"))
    return night and s.contrast >= LIT


def usable(shots: list[Shot]) -> tuple[list[Shot], list[str]]:
    keep, notes = [], []
    screens = [s for s in shots if s.utility]
    poor = [s for s in shots if not s.utility and s.quality < MIN_QUALITY and not lit_night(s)]
    keep = [s for s in shots if s not in screens and s not in poor]
    if not keep:  # never hand back an empty board
        return shots, notes
    if screens:
        notes.append(f"Left out {len(screens)} shot(s) that look like screenshots or documents.")
    if poor:
        notes.append(f"Left out {len(poor)} shot(s) that are very dark, flat or blurred.")
    return keep, notes


# --------------------------------------------------------------------------
# direction
# --------------------------------------------------------------------------

STOP = set("""a an the and or of in on at to for with into from my our me i we us it
this that these those some more less lot lots very really just make want like
about around through day days week weeks trip travel vlog video edit cut story
lean leaning focus focused mostly bit little please one two three four five six
seven eight nine ten first last""".split())


@dataclass
class Direction:
    text: str
    themes: list[str]
    used: list[str]
    ignored: list[str]
    labels: set[str]


def read_direction(text: str, shots: list[Shot]) -> Direction:
    words = re.findall(r"[a-z][a-z_'-]*", text.lower())
    vocab = {l for s in shots for l in s.labels}
    themes, used, ignored, labels = [], [], [], set()
    for w in words:
        if w in STOP:
            continue
        theme = w if w in THEMES else ALIASES.get(w)
        if theme:
            if theme not in themes:
                themes.append(theme)
                labels |= THEMES[theme]
            used.append(w)
        elif w in vocab or w.rstrip("s") in vocab:
            labels.add(w if w in vocab else w.rstrip("s"))
            themes.append(w)
            used.append(w)
        else:
            ignored.append(w)
    return Direction(text, themes, used, ignored, labels)


def matches(s: Shot, d: Direction) -> bool:
    return any(s.labels.get(l, 0) >= 0.2 for l in d.labels)


# --------------------------------------------------------------------------
# naming helpers
# --------------------------------------------------------------------------

def part_of_day(dt: datetime) -> str:
    h = dt.hour
    return ("Night" if h < 5 else "Morning" if h < 12 else "Afternoon" if h < 17
            else "Evening" if h < 21 else "Night")


def fmt_span(shots: list[Shot]) -> str:
    ts = [s.when for s in shots if s.when]
    if not ts:
        return f"{len(shots)} shot{'s' * (len(shots) != 1)}"
    a, b = min(ts), max(ts)
    if a.date() != b.date():
        span = f"{a.strftime('%b %-d')}–{b.strftime('%b %-d')}" if a.year == b.year \
            else f"{a.strftime('%b %Y')}–{b.strftime('%b %Y')}"
    elif a == b:
        span = a.strftime("%-I:%M %p")
    else:
        span = f"{a.strftime('%-I:%M')}–{b.strftime('%-I:%M %p')}"
    return f"{span} · {len(shots)} shot{'s' * (len(shots) != 1)}"


def distinctive_labels(group: list[Shot], everyone: list[Shot], k: int = 2) -> list[str]:
    """Labels over-represented in this group relative to the whole shoot."""
    def mean_conf(ss: list[Shot]) -> Counter:
        c: Counter = Counter()
        for s in ss:
            for l, v in s.labels.items():
                c[l] += v
        return Counter({l: v / max(1, len(ss)) for l, v in c.items()})
    g, a = mean_conf(group), mean_conf(everyone)
    scored = sorted(((g[l] - 0.5 * a[l], l) for l in g if g[l] >= 0.15), reverse=True)
    out: list[str] = []
    for _, l in scored:
        name = PRETTY.get(l, l.replace("_", " "))
        if name not in out:
            out.append(name)
        if len(out) == k:
            break
    return out


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def fmt_coord(p: tuple[float, float]) -> str:
    return f"{abs(p[0]):.3f}°{'N' if p[0] >= 0 else 'S'} {abs(p[1]):.3f}°{'E' if p[1] >= 0 else 'W'}"


def chrono(shots: list[Shot]) -> list[Shot]:
    return sorted(shots, key=lambda s: (s.when or datetime.max, s.order))


# --------------------------------------------------------------------------
# axis 1: time
# --------------------------------------------------------------------------

def by_time(shots: list[Shot], d: Direction) -> Option:
    seq = chrono(shots)
    timed = [s for s in seq if s.when]
    notes = []
    if len(timed) < len(seq) / 2:
        notes.append("Most clips carry no capture time, so this follows file order.")
        groups = [seq[i:i + 5] for i in range(0, len(seq), 5)]
        beats = [Beat(f"Part {i + 1}", fmt_span(g), g) for i, g in enumerate(groups)]
        return Option("time", "As it happened", "time",
                      "Filming order, in chunks of five — the clips carry no capture time.",
                      beats, notes, degraded=True)

    sessions: list[list[Shot]] = [[seq[0]]]
    for prev, s in zip(seq, seq[1:]):
        gap = (s.when - prev.when) if (s.when and prev.when) else timedelta(0)
        new_day = s.when and prev.when and s.when.date() != prev.when.date()
        if gap > SESSION_GAP or new_day:
            sessions.append([s])
        else:
            sessions[-1].append(s)
    sessions = _merge_smallest(sessions, MAX_BEATS, key=lambda g: g[0].when or datetime.max)

    days = sorted({s.when.date() for s in timed})
    beats, seen = [], Counter()
    for g in sessions:
        w = next((s.when for s in g if s.when), None)
        title = part_of_day(w) if w else "Undated"
        if len(days) > 1 and w:
            # "Day 3" only means something inside one trip.
            if (days[-1] - days[0]).days <= 21:
                title = f"Day {(w.date() - days[0]).days + 1} · {title}"
            else:
                title = f"{w.strftime('%b %-d')} · {title}"
        seen[title] += 1
        if seen[title] > 1:
            title += f" ({seen[title]})"
        beats.append(Beat(title, fmt_span(g), g, lean=any(s.lean for s in g)))

    span = f" over {len(days)} days" if len(days) > 1 else ""
    summary = f"Chronological: {len(beats)} sessions{span}, split wherever you stopped filming for 45+ minutes."
    return Option("time", "As it happened", "time", summary, beats, notes)


def _merge_smallest(groups: list[list[Shot]], cap: int, key) -> list[list[Shot]]:
    """Fold the smallest adjacent groups together until there are <= cap."""
    groups = [g for g in groups if g]
    while len(groups) > cap:
        i = min(range(len(groups) - 1), key=lambda j: len(groups[j]) + len(groups[j + 1]))
        groups[i:i + 2] = [groups[i] + groups[i + 1]]
    return groups


# --------------------------------------------------------------------------
# axis 2: place
# --------------------------------------------------------------------------

def _cluster_points(pts: list[tuple[float, float]], radius: float) -> list[int]:
    """Single-linkage clusters: points within `radius` metres chain together."""
    parent = list(range(len(pts)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if haversine_m(pts[i], pts[j]) <= radius:
                parent[find(i)] = find(j)
    roots = {}
    return [roots.setdefault(find(i), len(roots)) for i in range(len(pts))]


def by_place(shots: list[Shot], d: Direction, everyone: list[Shot]) -> Option:
    located = [s for s in shots if s.gps]
    unplaced = [s for s in shots if not s.gps]
    name, axis = "Place by place", "place"

    if len(located) < max(2, len(shots) // 3):
        return Option("place", name, axis,
                      "By place — but too few clips carry GPS, so it's one chapter.",
                      [Beat("Everything", fmt_span(chrono(shots)), chrono(shots))],
                      [f"Only {len(located)} of {len(shots)} shots carry a location — "
                       "iPhone camera originals do; screen recordings, downloads and "
                       "some exports don't."], degraded=True)

    # Clip-level points (shots in one file share a location).
    pts = sorted({s.gps for s in located})
    labels, radius = [0] * len(pts), PLACE_RADII_M[-1]
    for r in PLACE_RADII_M:
        labels = _cluster_points(pts, r)
        if len(set(labels)) <= MAX_BEATS:
            radius = r
            break
    where = dict(zip(pts, labels))
    groups: dict[int, list[Shot]] = {}
    for s in located:
        groups.setdefault(where[s.gps], []).append(s)

    if len(groups) < 2:
        spread = max((haversine_m(pts[0], p) for p in pts), default=0)
        return Option("place", name, axis,
                      "By place — but everything was filmed in one spot, so it's one chapter.",
                      [Beat(f"Around {fmt_coord(pts[0])}", fmt_span(chrono(shots)), chrono(shots))],
                      [f"Every clip was filmed within ~{max(spread, 10):.0f} m, so there is "
                       "only one place to chapter by."], degraded=True)

    # Chapters in the order you were there. A place you come back to later
    # gets a chapter of its own at that point in the day, under the same
    # letter -- folding the return into the first visit made the edit jump
    # back in time, which reads as a mistake, not a structure.
    letter = {id(g): chr(65 + i) for i, g in
              enumerate(sorted(groups.values(), key=lambda g: min((s.when for s in g if s.when), default=datetime.max)))}
    visits: list[tuple[int, list[Shot]]] = []   # (place key, shots of one visit)
    for g in groups.values():
        for v in _split_visits(chrono(g)):
            visits.append((id(g), v))
    visits.sort(key=lambda kv: kv[1][0].when or datetime.max)
    # Too many chapters: fold the shortest return visit into the nearest
    # visit to the same place, until it fits (or nothing can fold).
    while len(visits) > 2 * MAX_BEATS:
        cands = [(len(v), i) for i, (k, v) in enumerate(visits)
                 if sum(1 for kk, _ in visits if kk == k) > 1]
        if not cands:
            break
        _, i = min(cands)
        k, v = visits.pop(i)
        j = min((j for j, (kk, _) in enumerate(visits) if kk == k),
                key=lambda j: abs(((visits[j][1][0].when or datetime.max) - (v[0].when or datetime.max)).total_seconds())
                if visits[j][1][0].when and v[0].when else 0)
        visits[j] = (k, chrono(visits[j][1] + v))
    beats, seen = [], set()
    for k, g in visits:
        centre = (float(np.mean([s.gps[0] for s in g])), float(np.mean([s.gps[1] for s in g])))
        tags = distinctive_labels(g, everyone)
        title = f"Place {letter[k]}" + (" again" if k in seen else "") + (f" — {', '.join(tags)}" if tags else "")
        seen.add(k)
        beats.append(Beat(title, f"{fmt_coord(centre)} · {fmt_span(g)}", g, lean=any(s.lean for s in g)))
    if unplaced:
        beats.append(Beat("No location", fmt_span(unplaced), chrono(unplaced)))

    within = f"{radius / 1000:g} km" if radius >= 1000 else f"{radius} m"
    returns = len(visits) - len(groups)
    summary = (f"By place: {len(groups)} locations in the order you were there"
               + (f", {returns} of them revisited later in the day" if returns > 0 else "")
               + f" (clips within {within} are one place).")
    return Option("place", name, axis, summary, beats)


def _split_visits(g: list[Shot]) -> list[list[Shot]]:
    """One place's shots (in time order) -> one list per visit."""
    out: list[list[Shot]] = []
    for s in g:
        if out and s.when and out[-1][-1].when and s.when - out[-1][-1].when > SESSION_GAP:
            out.append([s])
        elif out:
            out[-1].append(s)
        else:
            out.append([s])
    return out


# --------------------------------------------------------------------------
# axis 3: subject
# --------------------------------------------------------------------------

def kmeans(x: np.ndarray, k: int, iters: int = 40, seed: int = 0) -> tuple[np.ndarray, float]:
    """Spherical k-means with k-means++ seeding. Returns (labels, inertia)."""
    rng = np.random.default_rng(seed)
    c = [x[rng.integers(len(x))]]
    for _ in range(1, k):
        d = np.min([1 - x @ ci for ci in c], axis=0).clip(0)
        c.append(x[rng.choice(len(x), p=d / d.sum())] if d.sum() > 0 else x[rng.integers(len(x))])
    c = np.array(c)
    for _ in range(iters):
        lab = np.argmax(x @ c.T, axis=1)
        new = np.array([x[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(k)])
        new /= np.linalg.norm(new, axis=1, keepdims=True) + 1e-9
        if np.allclose(new, c):
            break
        c = new
    return lab, float((1 - (x * c[lab]).sum(1)).sum())


def silhouette(x: np.ndarray, lab: np.ndarray) -> float:
    if len(set(lab.tolist())) < 2:
        return -1.0  # k-means collapsed (near-identical shots): no separation at all
    dist = 1 - x @ x.T
    scores = []
    for i in range(len(x)):
        same = lab == lab[i]
        if same.sum() < 2:
            scores.append(0.0)
            continue
        a = dist[i, same].sum() / (same.sum() - 1)
        b = min(dist[i, lab == j].mean() for j in set(lab) if j != lab[i])
        scores.append((b - a) / max(a, b, 1e-9))
    return float(np.mean(scores))


def by_subject(shots: list[Shot], d: Direction, everyone: list[Shot], vision: bool) -> Option:
    notes = []
    # A-roll first: you talking to the lens is a subject in its own right,
    # and it's what a vlog cuts away from and back to.
    on_cam = [s for s in shots if s.face_area >= 0.04]
    rest = [s for s in shots if s not in on_cam]
    lean = [s for s in rest if s.lean]
    rest = [s for s in rest if not s.lean]

    groups: list[tuple[str, list[Shot], bool]] = []
    if lean:
        groups.append((" · ".join(t.capitalize() for t in d.themes), lean, True))
    if on_cam:
        groups.append(("On camera", on_cam, False))

    if len(rest) >= 2:
        x = np.stack([s.vec for s in rest])
        best = (np.zeros(len(rest), int), -1.0)
        for k in range(2, min(MAX_BEATS - len(groups), len(rest) - 1) + 1):
            lab, _ = kmeans(x, k)
            sc = silhouette(x, lab)
            if sc > best[1]:
                best = (lab, sc)
        lab = best[0]
        clusters = [[s for s, l in zip(rest, lab) if l == j] for j in sorted(set(lab))]
        for g in sorted(clusters, key=lambda g: (chrono(g)[0].when or datetime.max)):
            tags = distinctive_labels(g, everyone) if vision else []
            groups.append((" & ".join(t.capitalize() for t in tags) or "", g, False))
    elif rest:
        groups.append(("", rest, False))

    beats, n_look = [], 0
    for title, g, is_lean in groups:
        if not title:
            n_look += 1
            title = f"Look {n_look}"
        beats.append(Beat(title, fmt_span(g), chrono(g), lean=is_lean))

    if not vision:
        notes.append("On-device Vision isn't available, so shots are grouped by colour "
                     "and light rather than by what's in them.")
    themes = len(beats) - bool(lean) - bool(on_cam)
    parts = ([f"{beats[0].title.lower()} first"] if lean else []) + (["you on camera"] if on_cam else []) + \
        ([f"{themes} visual theme{'s' * (themes != 1)}"] if themes else [])
    summary = f"By subject: {', then '.join(parts)} — ignoring when and where it was filmed."
    return Option("subject", "Subject by subject", "subject", summary, beats, notes,
                  degraded=not vision)


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def order_overlap(a: list[str], b: list[str]) -> float:
    """Share of shot pairs placed in the same relative order (Kendall-style)."""
    pos = {s: i for i, s in enumerate(b)}
    common = [s for s in a if s in pos]
    n = len(common)
    if n < 2:
        return 1.0
    agree = sum(1 for i in range(n) for j in range(i + 1, n) if pos[common[i]] < pos[common[j]])
    return agree / (n * (n - 1) / 2)


def build(clips: list[dict], direction: str, vision: bool,
          lean: tuple[list[str], list[str]] | None = None, cut: tuple[set, dict] | None = None,
          voiceover: dict | None = None, style: dict | None = None) -> dict:
    """Three proposals. `lean` = (theme names, Vision labels) when the chat
    model has already read the direction; otherwise keyword matching.
    With the creator's `voiceover` (voiceover.parse), a fourth comes first:
    one part per spoken line. `style` is the creator's answers to the
    style questions (brief.py): length, pace, opening."""
    everyone = shots_from_clips(clips, cut)
    shots, notes = usable(everyone)
    if lean is not None:
        d = Direction(direction, list(lean[0]), [], [], set(lean[1]))
    else:
        d = read_direction(direction, shots)
    for s in shots:
        s.lean = bool(d.labels) and matches(s, d)

    options = [by_time(shots, d), by_place(shots, d, everyone), by_subject(shots, d, everyone, vision)]
    best = {f"{c['id']}:{s['index']}": s["best_t"] for c in clips for s in c["shots"] if "best_t" in s}
    from . import brief, tempo
    pick, why = tempo.pick_story(options, shots)
    if vision:
        brief.one_per_look(options)
    if style:
        brief.shape(options, style, best, tempo.talking(clips, shots))

    base = [s.id for b in options[0].beats for s in b.shots]
    out = []
    for o in options:
        seq = [s.id for b in o.beats for s in b.shots]
        out.append({
            "key": o.key, "name": o.name, "axis": o.axis, "summary": o.summary,
            "notes": o.notes, "degraded": o.degraded,
            "same_order_as_time": None if o.key == "time" else round(order_overlap(seq, base), 2),
            "beats": [{
                "title": b.title, "detail": b.detail, "lean": b.lean,
                "shots": [{"id": s.id, "clip_id": s.clip_id, "start": s.start, "end": s.end,
                           "thumb": s.thumb, "lean": s.lean} for s in b.shots],
            } for b in o.beats],
        })

    if voiceover and voiceover.get("lines"):
        from . import voiceover as vo
        out.insert(0, vo.propose(voiceover, shots, best))
        pick, why = "voice", "It follows your voiceover."

    n_lean = sum(s.lean for s in shots)
    return {
        "direction": direction,
        "understood": {
            "themes": d.themes, "used": d.used, "ignored": d.ignored,
            "matched_shots": n_lean,
        },
        "notes": notes,
        "options": out,
        # the story to start from, read from the shoot (tempo.pick_story)
        "recommended": pick, "why": why,
    }
