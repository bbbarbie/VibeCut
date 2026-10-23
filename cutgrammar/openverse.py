"""Music and sound effects from the open web, as a TrackSource.

A creator with no music folder still needs a track. Openverse
(api.openverse.org) indexes Creative-Commons audio: music from Jamendo and
ccMixter, sound effects from Freesound. No account is needed for a few
searches an hour, which is all a remix does.

Only licences that allow commercial use *and* cutting the track into
another work are kept (CC0, CC BY, CC BY-SA). Jamendo's "no derivatives"
and "non-commercial" tracks are the majority of what a mood search returns,
and using one under a monetised post would break its terms, so they are
dropped at the search step. What a licence asks for (a credit line) is
kept on the track so the export can write it out.

Downloads and their features live under the cache dir; analysis is the
same `music.analyse` used for a local folder, cached the same way.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import music

API = "https://api.openverse.org/v1/audio/"
AGENT = "VibeCut/0.1 (open-source video editor)"
USABLE = ("cc0", "by", "by-sa")       # commercial use + derivatives allowed
PAGE = 20
MIN_TRACK_S = 40.0                    # shorter than a short-form edit is no use
MAX_TRACK_S = 420.0
SEARCH_TTL_S = 7 * 24 * 3600          # a search is cached a week; the catalogue barely moves
# Songs written for one day of the year. A mood search for "happy" returns
# "Happy Birthday" covers among its first results (a Sep 22 vlog got one on
# 2026-10-12); under footage of anything else the song names an occasion
# that isn't there, and the viewer hears that before any mood. Matched as
# whole words in the title, tags and genres.
OCCASIONS = re.compile(
    r"\b(birthdays?|bday|b-day|christmas|xmas|x-mas|navidad|noel|santa|jingle|carols?|"
    r"halloween|easter|thanksgiving|hanukkah|valentines?|weddings?|bridal|anniversary|"
    r"graduation|funeral|requiem|anthem|new year'?s?|feliz|cumplea\w*|geburtstag|anniversaire)\b",
    re.I)


def cache_dir() -> Path:
    root = Path(os.environ.get("VIBECUT_CACHE", str(Path.home() / ".cache" / "vibecut")))
    return root / "music" / "openverse"


def _get(params: dict, timeout: float = 20.0) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def occasion(rec: dict) -> bool:
    """True when the catalogue's own words tie the track to an occasion."""
    words = " ".join([rec.get("title") or "", *(rec.get("tags") or []), *(rec.get("genres") or [])])
    return bool(OCCASIONS.search(words))


def parse(results: list[dict], kind: str = "music") -> list[dict]:
    """API rows -> the few fields a remix needs, unusable licences dropped."""
    out = []
    for r in results:
        lic = (r.get("license") or "").lower()
        if lic not in USABLE:
            continue
        dur = (r.get("duration") or 0) / 1000.0
        if kind == "music" and not (MIN_TRACK_S <= dur <= MAX_TRACK_S):
            continue
        if kind == "sfx" and not (0.1 <= dur <= 4.0):
            continue
        rec = {
            "id": r["id"], "title": r.get("title") or "", "creator": r.get("creator") or "",
            "license": lic, "license_version": r.get("license_version") or "",
            "source": r.get("source") or "", "duration": round(dur, 2), "url": r.get("url"),
            "page": r.get("foreign_landing_url") or "",
            "tags": [t.get("name") for t in (r.get("tags") or []) if t.get("name")][:10],
            "genres": r.get("genres") or [],
        }
        if kind == "music" and occasion(rec):
            continue
        out.append(rec)
    return out


def credit(rec: dict) -> str:
    """The line a CC BY / BY-SA licence asks for. CC0 needs none; it is listed anyway."""
    lic = rec["license"].upper().replace("BY", "CC BY").replace("CC0", "CC0")
    ver = f" {rec['license_version']}" if rec.get("license_version") else ""
    page = f" — {rec['page']}" if rec.get("page") else ""
    return f"“{rec['title']}” by {rec['creator']} ({lic}{ver}){page}"


def search(query: str, kind: str = "music", pages: int = 1, source: str | None = None) -> list[dict]:
    """Search once per query (cached on disk), keeping only usable licences.

    Only an answer is cached. A search that failed (offline, a certificate
    the machine can't check) is not "no results": caching it as one kept
    music off for a week after the network came back."""
    d = cache_dir() / "search"
    d.mkdir(parents=True, exist_ok=True)
    key = re.sub(r"[^a-z0-9]+", "_", f"{kind}_{source or ''}_{query}".lower())[:80]
    f = d / f"{key}.json"
    if f.exists() and time.time() - f.stat().st_mtime < SEARCH_TTL_S:
        cached = json.loads(f.read_text())
        if cached:
            return cached
    rows: list[dict] = []
    failed = False
    for page in range(1, pages + 1):
        params = {"q": query, "license": ",".join(USABLE), "page_size": PAGE, "page": page}
        if kind == "music":
            params["category"] = "music"
        else:
            params["category"] = "sound_effect"
        if source:
            params["source"] = source
        try:
            rows += _get(params).get("results", [])
        except Exception:  # noqa: BLE001 -- offline or rate-limited: return what the cache has
            failed = True
            break
    out = parse(rows, kind)
    if failed and not out:
        try:   # an older answer beats none, however stale
            return json.loads(f.read_text())
        except (OSError, ValueError):
            return []
    f.write_text(json.dumps(out))
    return out


def fetch(rec: dict) -> Path | None:
    """Download one result into the cache (once). Returns the file, or None."""
    d = cache_dir() / ("sfx" if rec.get("duration", 99) < 4.0 else "tracks")
    d.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", rec["title"])[:40].strip("_") or "track"
    f = d / f"{slug}_{rec['id'][:8]}.mp3"
    if not f.exists():
        try:
            req = urllib.request.Request(rec["url"], headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=60) as r, open(f.with_suffix(".part"), "wb") as w:
                w.write(r.read())
            os.replace(f.with_suffix(".part"), f)
        except Exception:  # noqa: BLE001
            f.with_suffix(".part").unlink(missing_ok=True)
            return None
    side = f.with_suffix(".json")
    if not side.exists():
        side.write_text(json.dumps(rec))
    return f


class OpenverseSource(music.TrackSource):
    """Tracks found for a set of mood queries, analysed like a local folder.

    `queries` are plain words ("upbeat indie pop", "chill lofi"). Each is one
    API call; results are cached, so re-running a remix costs nothing.
    """

    def __init__(self, queries: list[str], per_query: int = 8,
                 progress=None) -> None:
        self.queries = queries
        self.per_query = per_query
        self.progress = progress
        self.records: dict[str, dict] = {}    # path -> licence record

    def list(self) -> list[music.Track]:
        picked: dict[str, dict] = {}
        for q in self.queries:
            for rec in search(q, "music", pages=2)[: self.per_query]:
                picked.setdefault(rec["id"], rec)
        files = []
        for rec in picked.values():
            f = fetch(rec)
            if f:
                files.append(f)
                self.records[str(f)] = rec
        folder = cache_dir() / "tracks"
        if not folder.exists():
            return []
        tracks = music.LocalFolderSource(str(folder), progress=self.progress).list()
        out = []
        for t in tracks:
            # the folder holds every track ever fetched, including ones from
            # searches cached before occasion songs were dropped
            if dress(t, self.records.get(t.path)) is not None and not occasion(t.meta["licence"]):
                out.append(t)
        return out


def dress(t: music.Track, rec: dict | None = None) -> music.Track | None:
    """A fetched track with its licence record and the catalogue's title (the
    file's tags are often mis-encoded); None when the record is gone."""
    rec = rec or _sidecar(t.path)
    if rec is None:
        return None
    t.meta = {**t.meta, "licence": rec}
    t.title = f"{rec['creator']} — {rec['title']}"
    return t


def _sidecar(path: str) -> dict | None:
    side = Path(path).with_suffix(".json")
    try:
        return json.loads(side.read_text())
    except (OSError, ValueError):
        return None


def sfx(query: str) -> Path | None:
    """One short sound effect (CC0/BY from Freesound) for a query, downloaded."""
    rows = search(query, "sfx", source="freesound")
    rows.sort(key=lambda r: (r["license"] != "cc0", r["duration"]))   # CC0 first, then shortest
    for rec in rows[:3]:
        f = fetch(rec)
        if f:
            return f
    return None
