"""The place axis follows the day: a place you come back to is a new chapter.

Two shoots that differ in one respect -- whether the morning's place is
visited again that evening -- must give the same chapters for everything
else, and the one with the return must stay in filming order
(`same_order_as_time` 1.0) with the return as its own chapter, under the
same letter. Folding the return into the first visit (the old behaviour)
made the edit jump back in time.

    python tests/test_axes.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_board import _clip  # noqa: E402

from web.backend import storyboard as sb  # noqa: E402

CAFE, MUSEUM = (35.6700, 139.7000), (35.7200, 139.7800)   # ~9 km apart


def clip(cid: str, hour: int, minute: int, where, label: str) -> dict:
    c = _clip(cid, hour, [label], 2)
    c["capture_time"] = f"2026-05-02T{hour:02d}:{minute:02d}:00+0900"
    c["gps"] = list(where)
    return c


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    day = [clip("cafe00000001", 9, 0, CAFE, "coffee"), clip("cafe00000002", 9, 20, CAFE, "coffee"),
           clip("museum000001", 12, 0, MUSEUM, "statue")]
    back = day + [clip("cafe00000003", 18, 0, CAFE, "coffee")]

    place = lambda clips: next(o for o in sb.build(clips, "", vision=True)["options"] if o["key"] == "place")  # noqa: E731
    a, b = place(day), place(back)
    titles = [x["title"].split(" — ")[0] for x in b["beats"]]
    check("a return visit is its own chapter, in the order of the day",
          titles == ["Place A", "Place B", "Place A again"], str(titles))
    check("…so the place edit keeps filming order", b["same_order_as_time"] == 1.0, str(b["same_order_as_time"]))
    check("two clips twenty minutes apart are still one visit",
          [len(x["shots"]) for x in a["beats"]] == [4, 2], str([len(x["shots"]) for x in a["beats"]]))
    check("everything else is unchanged by the return",
          [x["shots"] for x in b["beats"][:2]] == [x["shots"] for x in a["beats"]])
    check("the summary says a place was revisited", "revisited" in b["summary"], b["summary"])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
