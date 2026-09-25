"""What a measurement actually saw, and so what it is allowed to claim.

Adapted from the evidence discipline in montage-vlog-compiler (MIT; see
NOTICE): a conclusion is only as good as the way the footage was read.
Metadata says how long a clip is, not what is in it. A still -- and a
keyframe index at ~1/s is a row of stills -- shows the scene, the framing,
the exposure; it cannot show where a movement starts or lands, whether the
camera shook between two samples, or exactly which frame a cut is on.
Only a full-rate decode can. The sound is its own channel: picture evidence
says nothing about it, and vice versa.

So every finding names the readings it rests on, and a finding whose
readings the media doesn't carry is not given a verdict. It is marked
`pending` -- "not checked", never "fine" -- with the number kept beside it.
"""

from __future__ import annotations

META = "meta"      # container metadata: duration, size, rotation, streams
STILL = "still"    # individual frames, or keyframes sampled ~1/s
MOTION = "motion"  # every frame at native rate: movement, exact cut frames
AUDIO = "audio"    # the sound track, measured (not listened to)

ORDER = (META, STILL, MOTION, AUDIO)

WHAT = {
    META: "file metadata",
    STILL: "still frames",
    MOTION: "full-rate picture",
    AUDIO: "the sound track",
}


def available(media) -> set[str]:
    """The readings this Media carries.

    `media.load()` decodes every frame, so it carries motion. `load_index()`
    samples keyframes (its `times` are set): each sample is a still, and
    whatever happened between two of them was never seen.
    """
    out = {META}
    if getattr(media, "n_frames", 0):
        out.add(STILL)
        if getattr(media, "times", None) is None:
            out.add(MOTION)
    if getattr(media, "has_audio", False):
        out.add(AUDIO)
    return out


def missing(needs, have: set[str]) -> list[str]:
    return [lv for lv in ORDER if lv in set(needs) and lv not in have]


def describe(levels) -> str:
    return " + ".join(WHAT[lv] for lv in ORDER if lv in set(levels))
