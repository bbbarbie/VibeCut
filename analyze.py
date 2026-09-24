#!/usr/bin/env python3
"""Measure the editing grammar of one or more videos.

    python analyze.py vlog.mp4
    python analyze.py vlog.mp4 --json out.json
    python analyze.py refs/*.mp4 --quiet --json refs.json
"""

from __future__ import annotations

import argparse
import json
import sys

from cutgrammar import grammar, media, report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--json", metavar="PATH",
                    help="write machine-readable results here")
    ap.add_argument("--min-shot", type=float, default=0.4,
                    help="minimum shot length in seconds (default 0.4)")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress the terminal report")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    results = []
    for path in args.videos:
        try:
            m = media.load(path, verbose=not args.quiet)
        except Exception as e:  # noqa: BLE001
            print(f"  skipped {path}: {e}", file=sys.stderr)
            continue

        from cutgrammar import shots as shots_mod
        s = shots_mod.detect(m, min_shot_s=args.min_shot)
        r = grammar.analyze(m, s)
        results.append(r)

        if not args.quiet:
            print(report.to_text(r, color=not args.no_color))

    if args.json and results:
        payload = [json.loads(report.to_json(r)) for r in results]
        with open(args.json, "w") as fh:
            json.dump(payload if len(payload) > 1 else payload[0], fh,
                      indent=2, ensure_ascii=False)
        print(f"  wrote {args.json}")

    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
