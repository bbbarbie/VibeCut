"""cutgrammar -- measure the editing grammar of a video.

    from cutgrammar import media, shots, grammar, report

    m = media.load("vlog.mp4")
    r = grammar.analyze(m)
    print(report.to_text(r))
"""

__version__ = "0.1.0"

from . import features, grammar, media, report, shots  # noqa: F401
