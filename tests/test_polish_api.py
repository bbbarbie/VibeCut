"""The whole polish path, as the page drives it, on a face in the lower third.

A finished vertical clip with a face drawn in its lower third is opened;
the face boxes the on-device detector would report for it are supplied (this
test must run where there is no detector -- the detector itself is macOS's
Vision and is not what's under test). Then, exactly as the page does: a
click at 0:01 and "这里写上东京第一天" with a lower-third recipe. What the
page receives must have moved the words off the face, kept them inside the
safe area, and said so in the change. The control -- the same clip with the
face at the top -- must leave them in the lower third.

    python tests/test_polish_api.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = Path(tempfile.mkdtemp(prefix="vibecut-polish-api-"))
os.environ["VIBECUT_CACHE"] = str(TMP / "cache")
os.environ["VIBECUT_RECIPES"] = str(TMP / "recipes.json")

from polish import layout, recipe  # noqa: E402
from web.backend import polish_api as api  # noqa: E402

failures: list[str] = []
W, H = 1080, 1920


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def clip(path: Path, face) -> None:
    x, y, w, h = face
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x303a48:s={W}x{H}:r=30:d=3",
                    "-vf", f"drawbox=x={int(x * W)}:y={int(y * H)}:w={int(w * W)}:h={int(h * H)}:color=0xe0ac90:t=fill",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path)], check=True)


def run(face) -> dict:
    path = TMP / f"f{face[1]}.mp4"
    clip(path, face)
    api.open_video(api.OpenReq(path=str(path)))
    for _ in range(200):
        if api.P["job"] in ("ready", "error"):
            break
        time.sleep(0.1)
    # what Vision would report for this clip: the drawn face, every second
    api.P["faces"] = [{"t": float(t), "boxes": [list(face)]} for t in range(3)]
    return api.say(api.SayReq(t=1.0, x=0.5, y=0.8, text="这里写上东京第一天"))


def main() -> int:
    api.BOOK.save(recipe.Recipe(name="Mine", position="lower_third", size=0.06).check())
    low, top = (0.30, 0.66, 0.40, 0.22), (0.30, 0.10, 0.40, 0.22)
    s = layout.safe(W, H, 0.06)

    a = run(low)
    c = a["captions"][0]
    x, y, w, h = [v * k for v, k in zip(c["place"]["box"], (W, H, W, H))]
    fx, fy, fw, fh = layout.faces_px([list(low)], W, H)[0]
    check("the page gets the caption in the creator's recipe", c["recipe"]["name"] == "Mine" and c["text"] == "东京第一天")
    check("face in the lower third: the words moved off it",
          c["place"]["position"] != "lower_third" and layout.overlap((x, y, w, h), (fx, fy, fw, fh)) == 0,
          f"{c['place']['position']}: box y {y:.0f}-{y + h:.0f}, face y {fy:.0f}-{fy + fh:.0f}")
    check("…still inside the safe area", layout.inside((x, y, w, h), s, W, H))
    check("…and the change says it moved", "would have covered a face" in a["turns"][-1]["lines"][0]["text"],
          a["turns"][-1]["lines"][0]["text"])
    check("the face check was actually made", {k["key"]: k["verdict"] for k in c["place"]["checks"]}["caption_face"] == "ok")

    b = run(top)
    cb = b["captions"][0]
    check("face at the top: the words stay in the lower third", cb["place"]["position"] == "lower_third"
          and cb["place"]["moved"] is None, cb["place"]["position"])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
