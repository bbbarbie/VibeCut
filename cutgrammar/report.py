"""Rendering: terminal for a human, JSON for the pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict

from .grammar import BAD, OK, PENDING, WARN, Report

MARK = {OK: "  ok ", WARN: " warn", BAD: "  BAD", PENDING: "  n/c"}
COLOR = {OK: "\033[32m", WARN: "\033[33m", BAD: "\033[31m", PENDING: "\033[90m"}
RESET = "\033[0m"


def _fmt(value, unit: str) -> str:
    if value is None:
        return "-"
    if unit == "fraction":
        return f"{value * 100:.0f}%"
    if unit in ("s", "LUFS", "CV"):
        return f"{value:.2f} {unit}".strip()
    return f"{value:g} {unit}".strip()


def to_text(r: Report, color: bool = True) -> str:
    def c(v, s):
        return f"{COLOR[v]}{s}{RESET}" if color else s

    lines = [
        "",
        f"  {r.path}",
        f"  {r.duration:.1f}s · {r.fps:.2f} fps · {r.n_shots} shots · "
        f"{r.n_shots / max(r.duration, 1e-9) * 60:.1f} cuts/min",
        "",
    ]
    width = max((len(f.label) for f in r.findings), default=10)
    for f in r.findings:
        lines.append(f"  {c(f.verdict, MARK[f.verdict])}  "
                     f"{f.label.ljust(width)}  {_fmt(f.value, f.unit)}")
        lines.append(f"        {' ' * len(MARK[OK])}{f.detail}")
        lines.append("")

    bad, warn = len(r.by_verdict(BAD)), len(r.by_verdict(WARN))
    lines.append(f"  {bad} to fix · {warn} to look at · "
                 f"{len(r.by_verdict(OK))} fine")
    lines.append("")
    return "\n".join(lines)


def to_json(r: Report) -> str:
    """The machine-readable form -- this is what a style profile is built from."""
    return json.dumps({
        "path": r.path,
        "duration_s": r.duration,
        "fps": r.fps,
        "n_shots": r.n_shots,
        "shots": [
            {"i": s.index, "start_s": round(s.start_t, 3),
             "end_s": round(s.end_t, 3), "duration_s": round(s.duration, 3)}
            for s in r.shots
        ],
        "findings": [asdict(f) for f in r.findings],
    }, indent=2, ensure_ascii=False)
