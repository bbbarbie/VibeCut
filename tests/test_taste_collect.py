"""The taste collector picks a creator's good and ordinary video by likes per
view against their own videos, and measures a row into numbers only.

yt-dlp is stood in for (no network here); measuring runs on a real file
made with ffmpeg.

    python tests/test_taste_collect.py
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from taste import collect, measure  # noqa: E402

HEAD = "id,group,platform,url_or_file,creator,title,length_s,views,likes,counts_read_on,source,verdict,status,notes".split(",")


def _setup(tmp: Path) -> None:
    data = tmp / "data"
    data.mkdir()
    for p in ("long-youtube.csv", "short-reels.csv"):
        (data / p).write_text(",".join(HEAD) + "\n")
    (data / "candidate-creators.csv").write_text(
        "group,creator,platform,size_as_reported,why_listed,where_found,status\n"
        "long,Some One,YouTube,,,,candidate\nlong,Gone,YouTube,,,,struck\n")
    collect.DATA = data
    collect.GROUPS = {"long": data / "long-youtube.csv", "short": data / "short-reels.csv"}
    collect.CREATORS = data / "candidate-creators.csv"
    measure.OUT = tmp / "measurements"


def _video(i: int, views: int, likes: int, dur: int = 900, title: str = "") -> dict:
    return {"webpage_url": f"https://y/{i}", "title": title or f"paris vlog {i}", "channel": "Some One", "duration": dur,
            "view_count": views, "like_count": likes, "extractor_key": "Youtube"}


def test_discover_picks_against_the_creator() -> None:
    with tempfile.TemporaryDirectory() as t:
        _setup(Path(t))
        vids = {f"https://y/{i}": v for i, v in enumerate([
            _video(0, 1000, 10), _video(1, 2000, 100),   # 1: well watched, 5% -> good
            _video(2, 500, 5), _video(3, 400, 2),        # 3: less watched, 0.5% -> ordinary
            _video(4, 3000, 60), _video(5, 100, 50, dur=30),     # 5: too short for long, ignored
            _video(6, 5000, 500, title="fall haul + GRWM")])}    # 6: best ratio, but not a vlog
        def fake_json(args, timeout=120):
            q = args[-1]
            if q.startswith("ytsearch1:"):
                return [{"channel_url": "https://y/@someone"}]
            if q == "https://y/@someone/videos":
                return [{"url": u} for u in vids]
            return [vids[q]] if q in vids else []
        collect._json = fake_json
        collect.discover(lambda s: None)
        rows = list(csv.DictReader(collect.GROUPS["long"].open()))
        got = {r["verdict"]: r["url_or_file"] for r in rows}
        assert got == {"good": "https://y/1", "ordinary": "https://y/3"}, got
        assert [r["id"] for r in rows] == ["L001", "L002"]
        st = {r["creator"]: r["status"] for r in csv.DictReader(collect.CREATORS.open())}
        assert st == {"Some One": "discovered", "Gone": "struck"}, st


def test_measure_keeps_numbers_only() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        _setup(tmp)
        clip = tmp / "clip.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=3",
                        "-f", "lavfi", "-i", "color=c=red:size=320x180:rate=30:duration=3",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                        "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]", "-map", "2:a",
                        "-shortest", str(clip)], check=True)
        row = dict.fromkeys(HEAD, "")
        row.update(id="S001", group="short", url_or_file=str(clip), verdict="good", status="listed")
        collect.measure_one(row, lambda s: None)
        assert row["status"] == "measured", row
        rec = json.loads((measure.OUT / "S001.json").read_text())
        assert rec["pace"]["shots"] == 2, rec["pace"]
        assert "list" not in rec["transitions"] and rec["lufs"] is not None
        assert clip.exists()   # a local file is the creator's own; only downloads are deleted


def test_vlog_filter() -> None:
    assert collect.is_vlog({"title": "a week in tokyo"})
    assert collect.is_vlog({"title": "day in my life as a columbia student"})
    assert not collect.is_vlog({"title": "GRWM for my first day of class"})
    assert not collect.is_vlog({"title": "college haul vlog"})
    assert not collect.is_vlog({"title": "my favourite lip products"})


if __name__ == "__main__":
    test_vlog_filter()
    test_discover_picks_against_the_creator()
    test_measure_keeps_numbers_only()
    print("ok")
