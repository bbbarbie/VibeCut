"""A new video names itself from its clips: the days they were filmed and where.

sarah (2026-10-06): asking for a name before anything happens is one more
decision. So a video starts as "New video" and, once its clips are read, is
called e.g. "Sep 22 · Morningside Heights". Checks that the name moves with
the footage (another day, another place, a different name), that a single
café doesn't name a whole day, that without places the date alone is used,
and that a name the creator gives is never overwritten.

    python tests/test_auto_name.py
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-autoname-")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend import places  # noqa: E402
from web.backend import projects as pj  # noqa: E402

UNI, CAFE, MIDTOWN = (40.8075, -73.9626), (40.8051, -73.9655), (40.7549, -73.9840)
FOUND = {
    places.key(UNI): {"place": "Low Library", "area": "Morningside Heights", "city": "New York"},
    places.key(CAFE): {"place": "Hungarian Pastry Shop", "area": "Morningside Heights", "city": "New York"},
    places.key(MIDTOWN): {"place": "Bryant Park", "area": "Midtown", "city": "New York"},
}


def clip(when: str | None, gps=None) -> dict:
    return {"capture_time": when, "gps": list(gps) if gps else None}


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    day = [clip("2026-09-22T08:35:00-0400", UNI), clip("2026-09-22T12:10:00-0400", CAFE), clip("2026-09-22T19:00:00-0400", UNI)]
    got = pj.auto_name(day, FOUND)
    check("one day in one neighbourhood", got == "Sep 22 · Morningside Heights", got)
    check("the camera's own day, not UTC", pj.auto_name([clip("2026-09-22T23:30:00-0400")]) == "Sep 22")
    check("another day, another name", pj.auto_name([clip("2026-09-23T09:00:00-0400", UNI)], FOUND) == "Sep 23 · Morningside Heights")
    trip = day + [clip("2026-09-24T10:00:00-0400", MIDTOWN), clip("2026-09-24T11:00:00-0400", MIDTOWN),
                  clip("2026-09-24T13:00:00-0400", MIDTOWN)]
    got = pj.auto_name(trip, FOUND)
    check("days and neighbourhoods spread: a range and the city", got == "Sep 22–24 · New York", got)
    got = pj.auto_name([clip("2026-09-30T10:00:00-0400"), clip("2026-10-02T10:00:00-0400")])
    check("across a month", got == "Sep 30 – Oct 2", got)
    check("never one spot's name", "Library" not in pj.auto_name(day, FOUND) and "Pastry" not in pj.auto_name(day, FOUND))
    check("no places (off macOS, offline): the date alone", pj.auto_name(day) == "Sep 22")
    check("nothing to read: still a New video", pj.auto_name([clip(None)]) == "New video")

    pr = pj.create("")
    check("created without a name: New video, named by VibeCut", pr.name == "New video" and pr.auto_name)
    mine = pj.create("Tokyo weekend")
    check("a name given is the creator's", mine.name == "Tokyo weekend" and not mine.auto_name)
    check("and survives a reload", not pj.load(mine.id).auto_name and pj.load(pr.id).auto_name)

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_auto_name() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
