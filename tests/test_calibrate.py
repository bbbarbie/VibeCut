"""Calibration proposes a threshold that actually separates the two sets.

Fixtures from test_discriminates: the same picture with hard-synced sound
(bad) and with J-cuts (good), plus jittered copies so each side has a
distribution. The proposal for jl_cuts must fall between the two sides'
values with good below it; a finding identical on both sides must say "no
signal"; the record must be written and name its sets.

    python tests/test_calibrate.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import calibrate as cal  # noqa: E402
from tests.test_discriminates import build_fixtures  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def main() -> int:
    print("the numbers")
    check("AUC: all good above all bad is 1", cal.auc([3, 4], [1, 2]) == 1.0)
    check("AUC: interleaved is a coin toss", abs(cal.auc([1, 4], [2, 3]) - 0.5) < 0.01)
    check("AUC: all good below all bad is 0 (direction-free signal is |AUC − 0.5|)", cal.auc([1, 2], [3, 4]) == 0.0)
    cut, side, acc = cal.best_cut([0.1, 0.2, 0.3], [0.5, 0.6, 0.9])
    check("the cut sits between the sets, good below", 0.3 < cut < 0.5 and side == "below" and acc == 1.0, f"{cut} {side} {acc}")
    cut, side, acc = cal.best_cut([0.8, 0.9], [0.1, 0.3])
    check("…or good above", 0.3 < cut < 0.8 and side == "above", f"{cut} {side}")
    check("identical sets: no cut", cal.best_cut([1, 1], [1, 1])[0] is None)

    print("on the fixtures")
    with tempfile.TemporaryDirectory() as d:
        hard, good = build_fixtures(d)
        rows = [cal.measure(good, "good", Path(d) / "heads"), cal.measure(hard, "bad", Path(d) / "heads")]
        check("both measured, with findings", all(not r.error and r.values for r in rows), str([r.error for r in rows]))
        props = {p.key: p for p in cal.propose(rows)}
        jl = props["jl_cuts"]
        check("jl_cuts: the proposal falls between the two, good below",
              jl.cut is not None and jl.good[0] < jl.cut < jl.bad[0] and jl.good_is == "below" and jl.auc == 0.0,
              f"good {jl.good} bad {jl.bad} cut {jl.cut}")
        check("…and says it's thin, because it is", jl.thin and "thin" in jl.note, jl.note)
        same = next((p for p in props.values() if p.key != "jl_cuts" and p.good == p.bad), None)
        check("a finding identical on both sides says no signal", same is not None and "no signal" in same.note,
              str(same and (same.key, same.note)))
        check("the current guess is shown beside the proposal", jl.current == cal.CURRENT["jl_cuts"])
        jp, mp = cal.record(rows, list(props.values()), {"good": "J-cut fixture", "bad": "hard-sync fixture"},
                            Path(d) / "out", stamp="test")
        data = json.loads(jp.read_text())
        check("the record names its sets and carries every number",
              data["sets"]["good"] == "J-cut fixture" and len(data["videos"]) == 2 and any(p["key"] == "jl_cuts" for p in data["proposals"]))
        text = mp.read_text()
        check("the page is readable and changes nothing", "| jl_cuts |" in text and "Nothing here changes a threshold" in text)
        check("the 90 s head is cut once and reused", cal.head(good, Path(d) / "heads") == cal.head(good, Path(d) / "heads"))

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
