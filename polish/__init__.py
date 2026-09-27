"""polish: an edit that is already cut, and the creator pointing at it.

The one interaction this package exists for: the creator clicks a moment
on the player (a time *and* a place in the frame), says what they want
there -- "write 东京第一天 here", "a boom here", "make these words bigger"
-- and it happens, as an operation on the edit's layers they can see as a
diff and undo.

It is not auto-editing: the input is a finished video (or timeline), never a
pile of clips, and nothing is selected, ordered or cut here.

    anchor.py    the click: time, frame position, shot -- "here" made exact
    recipe.py    the creator's saved caption style, one click to reapply
    layout.py    where words go: off faces, inside the safe area, no orphans
    snap.py      an effect starts on movement or the beat, not the click
    timeline.py  layers as a turn log: apply, diff, undo
    parse.py     one sentence -> operations (rules first; a model optionally)
    probe.py     reading the finished video once: cuts, movement, beat
"""
