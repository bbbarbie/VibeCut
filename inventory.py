#!/usr/bin/env python3
"""Record a shoot folder by content hash, or check it hasn't changed since.

    python inventory.py build ~/Movies/Tokyo --out tokyo.inventory.json
    python inventory.py verify tokyo.inventory.json
    python inventory.py verify tokyo.inventory.json --root /Volumes/Card/Tokyo

The folder is only read. `verify` exits 1 when anything is missing,
changed, or new, and names each file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cutgrammar import inventory


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="hash and probe every video under a folder")
    b.add_argument("folder")
    b.add_argument("--out", required=True, metavar="PATH")
    v = sub.add_parser("verify", help="compare a folder against an inventory")
    v.add_argument("inventory")
    v.add_argument("--root", help="check this folder instead of the one recorded")
    v.add_argument("--json", metavar="PATH", help="also write the report here")
    args = ap.parse_args()

    try:
        if args.cmd == "build":
            inv = inventory.build(args.folder)
            out = Path(args.out).expanduser()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(inv, indent=2, ensure_ascii=False) + "\n")
            s = inv["summary"]
            print(f"  {s['files']} videos, {s['duration'] / 60:.1f} min, "
                  f"{s['probe_failed']} unreadable -> {out}")
            return 1 if s["probe_failed"] else 0

        rep = inventory.verify(json.loads(Path(args.inventory).expanduser().read_text()), args.root)
    except (OSError, ValueError) as e:
        print(f"  error: {e}", file=sys.stderr)
        return 2
    if args.json:
        Path(args.json).expanduser().write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n")
    s = rep["summary"]
    print(f"  {rep['status']}: {s['found']} found, {s['missing']} missing, "
          f"{s['changed']} changed, {s['unexpected']} not in the inventory")
    for p in rep["missing"]:
        print(f"    missing     {p}")
    for c in rep["changed"]:
        print(f"    changed     {c['path']}")
    for p in rep["unexpected"]:
        print(f"    unexpected  {p}")
    return 0 if rep["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
