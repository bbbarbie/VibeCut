"""Does the edit keep its song after the app restarts?

A track the bed or a Remix picked (an Openverse download, or one of the
backup songs) used to live only in memory; the board's set_music names it by
id, so after a restart nothing could find it and the edit lost its music,
though the file was still in the cache (sarah's Mac, 2026-10-18). Fixtures:
one fake Openverse download with its licence sidecar and one pack song,
analysed the way the bed reads them, then the memory wiped as a restart
would. Each must come back by id, dressed as when picked, its file servable,
and the board's track must be the one under the edit; an id with no file
stays missing.

    python tests/test_music_restart.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import wave

import numpy as np

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-restart-"))
os.environ.setdefault("VIBECUT_EXPORTS", os.path.join(os.environ["VIBECUT_CACHE"], "out"))
os.environ.setdefault("VIBECUT_BED", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import music, openverse, songpack  # noqa: E402
from web.backend import musiclib  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def _wav(path: str, seconds: float = 12.0, bpm: float = 100.0, sr: int = 16000) -> None:
    t = np.arange(int(seconds * sr)) / sr
    x = 0.05 * np.sin(2 * np.pi * 220 * t)
    for b in np.arange(0, seconds, 60.0 / bpm):
        x[int(b * sr):int(b * sr) + 40] += 0.5
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def main() -> int:
    ov = openverse.cache_dir() / "tracks"
    ov.mkdir(parents=True)
    song = ov / "Travelling_e67cdf1c.wav"
    _wav(str(song))
    rec = {"id": "e67cdf1c-0000", "title": "Travelling", "creator": "Ferlinka", "license": "by",
           "license_version": "4.0", "source": "jamendo", "duration": 12, "url": "", "page": "",
           "tags": ["travel"], "genres": []}
    song.with_suffix(".json").write_text(json.dumps(rec))
    picked = [t for t in music.LocalFolderSource(str(ov)).list() if openverse.dress(t)]

    s = songpack.songs_for("calm")[0]
    pd = songpack.cache_dir() / "calm"
    pd.mkdir(parents=True)
    _wav(str(pd / "tmp.wav"), bpm=s.bpm)
    os.rename(pd / "tmp.wav", pd / f"{s.id}.m4a")   # the folder reader goes by the name; ffmpeg reads the wav inside
    pack = [t for t in music.LocalFolderSource(str(pd)).list() if songpack.dress(t)]

    check("the fixtures were read like the bed reads them", len(picked) == 1 and len(pack) == 1)
    want, want_pack = picked[0], pack[0]

    print("after a restart")
    musiclib.STATE["tracks"] = []
    got = musiclib.find(want.id)
    check("the Openverse song is found by its id", got is not None and got.path == want.path)
    check("with its catalogue title and licence", got is not None and got.title == "Ferlinka — Travelling"
          and got.meta.get("licence", {}).get("creator") == "Ferlinka", got.title if got else "")
    check("and the same beat", got is not None and got.bpm == want.bpm and len(got.energy) == len(want.energy))
    check("it joins the list, so the next poll doesn't look again", any(t.id == want.id for t in musiclib.STATE["tracks"]))
    check("its file can be played", musiclib.path_for(want.id) == want.path)
    gp = musiclib.find(want_pack.id)
    check("a backup song is found too, titled as one", gp is not None and gp.title == f"{s.title} (VibeCut)",
          gp.title if gp else "")
    check("an id with no file stays missing", musiclib.find("000000000000") is None
          and "000000000000" in musiclib._MISSING)
    musiclib.use(want_pack.id)
    check("a found song can be put under the edit", musiclib.current() is not None and musiclib.current().id == want_pack.id)

    print("the edit's own track")
    from web.backend import app as backend
    musiclib.STATE["tracks"] = []
    backend.SESSION.board = {"beats": [], "music": {"track": want.id, "in": 0.0}}
    t = backend._track()
    check("the board's set_music track is under the edit again", t is not None and t.id == want.id)
    pub = backend._music_public()
    check("and the session shows it", pub is not None and pub["title"] == "Ferlinka — Travelling", json.dumps(pub))
    backend.SESSION.board = None

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
