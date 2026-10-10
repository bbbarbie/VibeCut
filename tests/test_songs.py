"""The song under the edit (songs.py): picked by tempo and shape, cuts on its
beat, quieter under talking. No network: the library is never searched.

Each property is checked by two cases that differ in one respect: a song at
the edit's tempo against one far off it; a talking shot against a silent
one; music under a voice against music under nothing.

    python tests/test_songs.py
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-songs-")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import numpy as np  # noqa: E402

from cutgrammar import music as mu  # noqa: E402
from web.backend import audiomix  # noqa: E402
from web.backend import board as bd  # noqa: E402
from web.backend import songs  # noqa: E402
from web.backend import storyboard as sb  # noqa: E402
from web.backend import timeline  # noqa: E402


def clip(i: int, dur: float, voice: float = 0.0) -> dict:
    n = int(dur) + 1
    return {
        "id": f"c{i}", "name": f"IMG_{i:04d}.MOV", "duration": dur, "path": f"/nowhere/{i}.mov",
        "capture_time": f"2026-09-22T{8 + i:02d}:00:00", "gps": [40.0, -74.0],
        "sound": {"voice": [voice] * n, "music": [0.0] * n},
        "shots": [{"index": 0, "start": 0.0, "end": dur, "thumb": "t.jpg", "quality": 0.7, "best_t": dur / 2,
                   "activity": 20.0 + 5 * i, "labels": [], "faces": 0, "face_area": 0.0,
                   "embedding": [float(i == k) for k in range(64)]}],
    }


def board_of(windows: list[tuple[str, float, float]]) -> dict:
    return {"option": "t", "name": "t", "structure": "", "beats": [
        {"id": "b1", "title": "Morning", "detail": "", "shots": [{"id": i, "start": a, "end": z} for i, a, z in windows[:3]]},
        {"id": "b2", "title": "Night", "detail": "", "shots": [{"id": i, "start": a, "end": z} for i, a, z in windows[3:]]},
    ]}


def track(path: str, bpm: float | None, dur: float = 120.0, tags: list[str] | None = None) -> mu.Track:
    t = mu.Track(path=path, duration=dur, bpm=bpm, energy=np.linspace(0.2, 1.0, int(dur)).astype(np.float32),
                 title=os.path.basename(path), meta={"tempo": {"phase": 0.1} if bpm else {}})
    if tags is not None:
        t.meta["licence"] = {"title": t.title, "creator": "someone", "tags": tags, "genres": [],
                             "license": "by", "license_version": "4.0", "page": "https://example.org/x"}
    return t


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    clips = [clip(i, 9.0, voice=0.9 if i == 1 else 0.0) for i in range(6)]
    cat = bd.Catalog.from_clips(clips)
    board = board_of([(f"c{i}:0", 1.0, 1.0 + d) for i, d in enumerate([2.3, 3.1, 1.7, 2.6, 4.2, 2.05])])

    print("tempo")
    check("a 120 BPM song fits quick cuts", songs.tempo_fit(120, "fast") == 1.0, f"{songs.tempo_fit(120, 'fast'):.2f}")
    check("…and not calm ones", songs.tempo_fit(120, "calm") < 0.5, f"{songs.tempo_fit(120, 'calm'):.2f}")
    check("a 62 BPM song cut on its eighths fits quick cuts too", songs.tempo_fit(62, "fast") == 1.0)

    print("ranking")
    lively = track("/s/lively.mp3", 122, tags=["upbeat", "pop"])
    slow = track("/s/slow.mp3", 70, tags=["piano", "calm"])
    short = track("/s/short.mp3", 122, dur=10.0, tags=["upbeat"])
    ranked = songs.rank(board, cat, "fast", [slow, short, lively])
    check("quick cuts: the lively song first", ranked[0] is lively, str([t.title for t in ranked]))
    ranked = songs.rank(board, cat, "calm", [lively, slow])
    check("calm cuts: the slow song first", ranked[0] is slow, str([t.title for t in ranked]))
    check("a song shorter than the edit isn't offered", short not in ranked)

    print("cuts on the beat")
    talk = {"c1:0"}
    ops = songs.use_ops(board, cat, lively, talk)
    b = board
    for op in ops:
        b, _ = bd.apply(b, op, cat, None, new_id=lambda: "")
    p = 60 / 122
    lens = [e["end"] - e["start"] for bt in b["beats"] for e in bt["shots"]]
    cuts = np.cumsum(lens)
    off = np.abs(cuts / p - np.round(cuts / p)) * p
    check("every cut lands on a beat", float(off.max()) < 0.002, f"worst {off.max() * 1000:.1f} ms")
    moved = [abs(x - y) for k, (x, y) in enumerate(zip(lens, [2.3, 3.1, 1.7, 2.6, 4.2, 2.05])) if k != 1]
    check("no silent shot moves more than half a beat", max(moved) <= p / 2 + 0.002, f"{max(moved):.3f} s")
    check("the talking shot only grows, by under a beat", 3.1 <= lens[1] < 3.1 + p, f"{lens[1]:.3f} s")
    bed = b["music"]
    check("the song starts on its own beat", abs(((bed["in"] - 0.1) / p) - round((bed["in"] - 0.1) / p)) < 1e-3,
          f"in {bed['in']}")
    check("the bed ducks under speech", bed.get("duck_speech") is True)

    nobeat = track("/s/free.mp3", None, tags=["ambient"])
    ops2 = songs.use_ops(board, cat, nobeat, talk)
    check("a song with no steady beat leaves the cuts alone", [o["op"] for o in ops2] == ["set_music"])

    print("quieter under talking")
    items = timeline.build(b, {c["id"]: c for c in clips}, lively)["items"]
    ducks = songs.speech_ducks(items, {c["id"]: c for c in clips})
    sh = next(it for it in items if it["shot_id"] == "c1:0")
    check("one duck, over the talking shot", len(ducks) == 1 and ducks[0][0] <= sh["seq_start"] + 0.01
          and ducks[0][1] >= sh["seq_end"] - 0.01, str(ducks))
    sr = audiomix.SR
    n = int(items[-1]["seq_end"] * sr)
    env = audiomix.duck_envelope(n, songs.resolve(bed, items, {c["id"]: c for c in clips})["duck"])
    mid = int((sh["seq_start"] + sh["seq_end"]) / 2 * sr)
    check("the song is quieter under the voice than elsewhere", env[mid] < 0.5 and env[-1] == 1.0,
          f"{env[mid]:.2f} vs {env[-1]:.2f}")
    check("no talking, no ducks", songs.resolve({"duck_speech": False}, items, {})
          == {"duck_speech": False})

    print("the beat grid follows the song's start")
    grid = timeline.build(b, {c["id"]: c for c in clips}, lively)["grid"]
    first_cut = float(cuts[0])
    k = (first_cut - grid["phase"]) / p
    check("the timeline's beats are the beats the cuts were put on", abs(k - round(k)) < 0.01,
          f"phase {grid['phase']}")

    print("words")
    check("plain reason, no jargon", "BPM" not in songs.why(lively) and "beat" in songs.why(lively),
          songs.why(lively))
    check("a free song carries its credit line", "CC BY 4.0" in (songs.credit(lively) or ""),
          songs.credit(lively) or "")
    check("own songs need no credit", songs.credit(track("/s/mine.mp3", 100)) is None)

    print("own song")
    import io
    wav = os.path.join(os.environ["VIBECUT_CACHE"], "click.wav")
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "aevalsrc='if(lt(mod(t,0.5),0.03),sin(2*PI*1000*t),0)':s=16000:d=40", wav], check=True)
    with open(wav, "rb") as fh:
        t = songs.add_own("My song.wav", io.BytesIO(fh.read()))
    check("an added song is read and kept", songs.find(t.id) is t and t.meta.get("own"), t.title)
    check("its beat is found", t.bpm is not None and abs(t.bpm - 120) < 2, str(t.bpm))
    try:
        songs.add_own("notes.txt", io.BytesIO(b"x"))
        check("a non-song file is refused", False)
    except ValueError as e:
        check("a non-song file is refused", True, str(e))

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
