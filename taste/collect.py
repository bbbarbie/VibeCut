"""Fill the taste set in one run: counts, downloads, measurements, deletes.

Run on sarah's Mac (yt-dlp, ffmpeg, Vision for the words on screen), from
the repo root:

    .venv/bin/python -m taste.collect            # discover, then measure
    .venv/bin/python -m taste.collect --only measure

Two passes, both resumable (a row's status says how far it got):

- discover: for every creator in data/candidate-creators.csv still marked
  `candidate`, list their recent videos of the group's kind (long uploads,
  or Shorts / TikToks), keep the vlogs, read views and likes, and add their
  PER_CREATOR most-watched as good examples. The list is vloggers only, and
  a popular vlogger's vlogs are all worth learning from (sarah, 2026-10-20).
- measure: every row with a link, a verdict and status `listed` is
  downloaded at 480p (long: the first LONG_S seconds), measured
  (taste.measure + words on screen through Vision), and deleted. Only the
  numbers stay, in measurements/<id>.json.

Nothing of anyone's video is kept, and nothing here calls a paid model.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from cutgrammar import media, style
from . import measure as measure_mod

HERE = Path(__file__).parent
DATA = HERE / "data"
GROUPS = {"long": DATA / "long-youtube.csv", "short": DATA / "short-reels.csv"}
CREATORS = DATA / "candidate-creators.csv"
PREFIX = {"long": "L", "short": "S"}

RECENT = 12            # vlogs looked at per creator
PER_CREATOR = 3        # ...of which the most watched are learnt from
LONG_S = 600.0         # a long vlog is measured on its first ten minutes
LONG_RANGE = (300, 2700)   # what counts as a long vlog, seconds
SHORT_MAX = 180            # ...and a short one
FORMAT = "bv*[height<=480]+ba/b[height<=480]/b"
BRANCH = "origin/claude/vlog-taste-model-i4z3mi"

# sarah, 2026-10-20: "filter mainly for vlogs". A creator's channel also
# carries hauls, get-ready-with-me, Q&As and podcasts; those are cut by
# other rules (talking to a mirror, a product on a table) and would teach
# the wrong rhythm. A title has to say it is a vlog, and must not say it
# is one of those.
VLOG = ("vlog", "day in my life", "day in the life", "diml", "a day ", "spend the day", "week in",
        "weekend in", "days in", "trip", "travel", "a week", "24 hours", "morning routine",
        "come with me", "life in", "living in", "college", "uni ", "semester", "study with me")
NOT_VLOG = ("grwm", "get ready with me", "haul", "q&a", "q & a", "podcast", "reaction", "review",
            "unboxing", "makeup tutorial", "storytime", "try on", "try-on", "ranking", "challenge")


def is_vlog(d: dict) -> bool:
    text = " ".join([d.get("title") or "", " ".join(d.get("tags") or []),
                     (d.get("description") or "")[:400]]).lower() + " "
    return any(w in text for w in VLOG) and not any(w in text for w in NOT_VLOG)


def ytdlp() -> str:
    exe = shutil.which("yt-dlp") or "/usr/local/bin/yt-dlp"
    if not Path(exe).exists():
        raise SystemExit("yt-dlp isn't installed")
    return exe


def _json(args: list[str], timeout: int = 120) -> list[dict]:
    p = subprocess.run([ytdlp(), "-j", "--skip-download", "--no-warnings", *args],
                       capture_output=True, text=True, timeout=timeout)
    out = []
    for line in p.stdout.splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def info(url: str) -> dict | None:
    got = _json(["--no-playlist", url])
    return got[0] if got else None


def _rows(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def _save(path: Path, head: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=head)
        w.writeheader()
        w.writerows(rows)


def _next_id(group: str, rows: list[dict]) -> str:
    n = max([int(r["id"][1:]) for r in rows if r.get("id", "")[1:].isdigit()] or [0])
    return f"{PREFIX[group]}{n + 1:03d}"


def _counts(row: dict, d: dict) -> None:
    row["creator"] = row.get("creator") or d.get("channel") or d.get("uploader") or ""
    row["title"] = row.get("title") or (d.get("title") or "")[:120]
    row["length_s"] = str(d.get("duration") or "")
    row["views"] = str(d.get("view_count") or "")
    row["likes"] = str(d.get("like_count") or "")
    row["counts_read_on"] = time.strftime("%Y-%m-%d")


def _ratio(d: dict) -> float | None:
    v, l = d.get("view_count"), d.get("like_count")
    return l / v if v and l is not None else None


# --- what Claude added on the branch -----------------------------------------

def _origin_rows(path: Path) -> list[dict]:
    """The branch's copy of a list: links sarah sent in the thread, strikes."""
    try:
        rel = path.relative_to(HERE.parent).as_posix()
    except ValueError:
        return []
    p = subprocess.run(["git", "show", f"{BRANCH}:{rel}"], capture_output=True, text=True, cwd=HERE.parent)
    return list(csv.DictReader(p.stdout.splitlines())) if p.returncode == 0 else []


STAGE = {"": 0, "listed": 1, "failed": 1, "not a vlog": 2, "measured": 3}


def sync(log) -> None:
    """Bring in what the branch has without losing what this Mac measured."""
    for path in [*GROUPS.values()]:
        head, rows = _rows(path)
        by_url = {r["url_or_file"]: r for r in rows}
        for o in _origin_rows(path):
            mine = by_url.get(o["url_or_file"])
            if mine is None:
                o = {k: o.get(k, "") for k in head}
                if any(r["id"] == o["id"] for r in rows):
                    o["id"] = _next_id(o["group"], rows)
                rows.append(o)
                log(f"new from the thread: {o['id']} {o['url_or_file']}")
            elif STAGE.get(o.get("status", ""), 0) > STAGE.get(mine.get("status", ""), 0):
                mine.update({k: o.get(k, "") for k in head})
            elif o.get("verdict") and o["verdict"] != mine.get("verdict"):
                mine["verdict"] = o["verdict"]     # sarah's call, made in the thread
        _save(path, head, rows)
    head, creators = _rows(CREATORS)
    known = {(c["group"], c["creator"]): c for c in creators}
    for o in _origin_rows(CREATORS):
        c = known.get((o["group"], o["creator"]))
        if c is None:
            creators.append({k: o.get(k, "") for k in head})
        elif o["status"] in ("struck", "dropped") or o["status"].startswith("skip"):
            c["status"] = o["status"]          # struck or skipped in the thread
        elif o["status"] != "candidate" and c["status"] == "candidate":
            c["status"] = o["status"]
    # a creator whose picks all turned out not to be vlogs is looked at again
    kept = {r["creator"] for path in GROUPS.values() for r in _rows(path)[1]
            if r.get("source") == "web" and r.get("status") != "not a vlog"}
    for c in creators:
        if c["status"] == "discovered" and c["creator"] not in kept:
            c["status"] = "candidate"
    _save(CREATORS, head, creators)


# --- discover ---------------------------------------------------------------

def _channel(name: str, platform: str, group: str) -> str | None:
    """Where a creator's recent videos of this kind are listed."""
    if platform.lower() == "tiktok" and " " not in name.strip():
        return f"https://www.tiktok.com/@{name.strip().lstrip('@')}"
    hit = _json(["--flat-playlist", "--playlist-items", "1", f"ytsearch1:{name} vlog"])
    url = hit[0].get("channel_url") if hit else None
    if not url and hit and hit[0].get("url"):
        url = (info(hit[0]["url"]) or {}).get("channel_url")
    if not url:
        return None
    return url.rstrip("/") + ("/videos" if group == "long" else "/shorts")


def _fits(group: str, d: dict) -> bool:
    s = d.get("duration") or 0
    return LONG_RANGE[0] <= s <= LONG_RANGE[1] if group == "long" else 0 < s <= SHORT_MAX


def discover(log) -> None:
    head, creators = _rows(CREATORS)
    for c in creators:
        if c.get("status") != "candidate":
            continue
        group, name = c["group"], c["creator"]
        where = _channel(name, c.get("platform", ""), group)
        if not where:
            c["status"] = "not found"
            log(f"{name}: channel not found")
            continue
        flat = _json(["--flat-playlist", "--playlist-items", f"1:{RECENT * 4}", where], timeout=300)
        vids = []
        for e in flat:
            u = e.get("url") or e.get("webpage_url")
            if not u:
                continue
            d = info(u)
            if d and _fits(group, d) and is_vlog(d) and _ratio(d) is not None:
                vids.append(d)
            if len(vids) >= RECENT:
                break
        if not vids:
            c["status"] = "no vlogs"
            log(f"{name}: no vlogs among the recent videos at {where}")
            continue
        # sarah, 2026-10-20: a big vlogger's vlogs are all good examples, so
        # learn from their most-watched recent ones rather than pick a weak one.
        picks = sorted(vids, key=lambda d: d["view_count"], reverse=True)[:PER_CREATOR]
        hd, rows = _rows(GROUPS[group])
        have = {r["url_or_file"] for r in rows}
        for d in picks:
            url = d.get("webpage_url")
            if url in have:
                continue
            row = {k: "" for k in hd}
            row.update(id=_next_id(group, rows), group=group, platform=d.get("extractor_key", "").lower(),
                       url_or_file=url, source="web", verdict="good", status="listed",
                       notes=f"top {PER_CREATOR} by views of {len(vids)} recent vlogs; channel {d.get('channel_follower_count') or '?'}")
            _counts(row, d)
            rows.append(row)
        _save(GROUPS[group], hd, rows)
        c["status"] = "discovered"
        log(f"{name}: " + "; ".join(repr((d.get('title') or '')[:40]) for d in picks))
        _save(CREATORS, head, creators)
    _save(CREATORS, head, creators)


# --- measure ----------------------------------------------------------------

def _words(path: str, tmp: Path, limit_s: float):
    """Words on screen through the Mac's Vision; None elsewhere."""
    try:
        from web.backend import reference
        return reference.text_events(path, tmp / "text", limit_s)
    except Exception:
        return None


def measure_one(row: dict, log) -> None:
    url = row["url_or_file"]
    group = row["group"]
    if url.startswith("http") and (not row.get("views") or row.get("source") == "web"):
        d = info(url)
        if d:
            if not row.get("views"):
                _counts(row, d)
            # picked before the vlog filter, or by a loose title: checked with its tags and description
            if row.get("source") == "web" and not is_vlog(d):
                row["status"] = "not a vlog"
                log(f"{row['id']}: not a vlog ({row['title'][:40]!r}), skipped")
                return
    tmp = Path(tempfile.mkdtemp(prefix="taste-"))
    try:
        if url.startswith("http"):
            cmd = [ytdlp(), "-q", "--no-warnings", "--no-playlist", "-f", FORMAT, "-o", str(tmp / "v.%(ext)s")]
            if group == "long":
                cmd += ["--download-sections", f"*0-{int(LONG_S)}"]
            subprocess.run(cmd + [url], check=True, timeout=1800)
            path = str(next(p for p in tmp.iterdir() if p.name.startswith("v.")))
        else:
            path = url
        limit = LONG_S if group == "long" else None
        m = media.load(path, limit_s=limit)
        s = style.learn(m, text=_words(path, tmp, min(m.duration, limit or m.duration)))
        s["transitions"].pop("list", None)
        rec = {"id": row["id"], "source_name": Path(path).name, "group": group, **s,
               "lufs": media.loudness_lufs(path), "measured_s": round(m.duration, 2),
               "ending_is_cutoff": bool(limit and m.duration >= limit - 1)}
        measure_mod.OUT.mkdir(exist_ok=True)
        (measure_mod.OUT / f"{row['id']}.json").write_text(json.dumps(rec, indent=1, default=float))
        row["status"] = "measured"
        log(f"{row['id']}: {s['pace']['shots'] if s.get('pace') else '?'} shots, "
            f"{(s.get('pace') or {}).get('median_s', '?')} s median, {rec['lufs']} LUFS")
    except Exception as e:   # one bad link (private, login-only) must not stop the batch
        row["status"] = "failed"
        row["notes"] = (row.get("notes", "") + f"; failed {time.strftime('%Y-%m-%d')}: {type(e).__name__}").strip("; ")
        log(f"{row['id']}: failed ({type(e).__name__}: {str(e)[:120]})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def measure_all(log) -> None:
    off = {c["creator"].lower() for c in _rows(CREATORS)[1]
           if c["status"] in ("struck", "dropped") or c["status"].startswith("skip")}
    for group, path in GROUPS.items():
        head, rows = _rows(path)
        for row in rows:
            if row.get("source") == "web" and row.get("creator", "").lower() in off:
                continue
            if row.get("status") == "listed" and row.get("verdict") in ("good", "ordinary") and row.get("url_or_file"):
                measure_one(row, log)
                _save(path, head, rows)    # after each, so a stop loses one video at most


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["discover", "measure"])
    a = ap.parse_args()
    log = lambda s: print(s, flush=True)
    sync(log)
    if a.only != "measure":
        discover(log)
    if a.only != "discover":
        measure_all(log)
    log("done")


if __name__ == "__main__":
    main()
