"""The open-web music source: only usable licences get through, and a
search is one request, then the cache. No network is touched here.

    python tests/test_openverse.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

failures: list[str] = []


def check(name: str, cond: bool, got: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
    if not cond:
        failures.append(name)


def row(i: int, lic: str, dur_s: float, title: str = "t") -> dict:
    return {"id": f"id{i}", "title": title, "creator": "who", "license": lic, "license_version": "3.0",
            "source": "jamendo", "duration": dur_s * 1000, "url": f"https://x/{i}.mp3",
            "foreign_landing_url": f"https://x/{i}", "tags": [{"name": "happy"}], "genres": []}


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        os.environ["VIBECUT_CACHE"] = d
        from cutgrammar import openverse as ov

        print("licences")
        rows = [row(1, "by-nc-nd", 120), row(2, "by", 120), row(3, "cc0", 120), row(4, "by-sa", 120),
                row(5, "by-nc", 120), row(6, "by", 20), row(7, "by", 900)]
        got = ov.parse(rows)
        check("non-commercial and no-derivatives tracks are dropped",
              {r["id"] for r in got} == {"id2", "id3", "id4"}, str([r["id"] for r in got]))
        check("too short and too long for a short are dropped", all(40 <= r["duration"] <= 420 for r in got),
              str([r["duration"] for r in got]))
        c = ov.credit(got[0])
        check("the credit line names the work, the maker, the licence and the page",
              "“t” by who (CC BY 3.0)" in c and "https://x/2" in c, c)

        print("search cache")
        calls = []

        def fake_get(params, timeout=20.0):
            calls.append(params)
            return {"results": rows}

        ov._get = fake_get
        a = ov.search("upbeat pop")
        b = ov.search("upbeat pop")
        check("one request per query; the second read is the cache", len(calls) == 1 and a == b,
              f"{len(calls)} request(s)")
        check("the request asks only for usable licences", calls[0]["license"] == "cc0,by,by-sa",
              calls[0]["license"])
        cached = json.loads(next(Path(d, "music", "openverse", "search").glob("*.json")).read_text())
        check("the cache holds the filtered rows, not the raw ones", len(cached) == 3, str(len(cached)))

        print("sfx")
        sfx_rows = [row(8, "by", 0.5), row(9, "cc0", 0.9), row(10, "cc0", 0.3)]

        def fake_get_sfx(params, timeout=20.0):
            return {"results": sfx_rows}

        ov._get = fake_get_sfx
        got = ov.search("whoosh", "sfx", source="freesound")
        check("sound effects keep only short files", {r["id"] for r in got} == {"id8", "id9", "id10"},
              str([r["id"] for r in got]))
    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
