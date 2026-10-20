"""The server inside VibeCut.app.

PyInstaller freezes this file with web.backend; the app's launcher
(VibeCut.swift) starts it on a free port and shows the page in a window.
"""

import multiprocessing
import os
import sys
import threading
import time


def _follow_launcher(parent: int) -> None:
    # If the window is force-quit or crashes, nobody stops this server, so
    # it stops itself when the launcher that started it is gone.
    while True:
        time.sleep(2)
        if os.getppid() != parent:
            os._exit(0)


def selftest(clip: str) -> int:
    """Read one clip the way an import does, through the frozen worker
    processes and the bundled helpers. The build runs this before zipping."""
    import json

    from web.backend import indexer, sound

    rec = indexer.pool().submit(indexer.index_clip, clip).result()
    out = {"shots": len(rec["shots"]), "vision": indexer.add_vision([rec]), "sound": sound.add_sound([rec])}
    print(json.dumps(out))
    return 0 if out["shots"] and out["vision"] == "vision" else 1


def main() -> int:
    if sys.argv[1:2] == ["--selftest"]:
        return selftest(sys.argv[2])
    import uvicorn

    from web.backend.app import app

    threading.Thread(target=_follow_launcher, args=(os.getppid(),), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("VIBECUT_PORT", 8765)),
                log_level="warning")
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()   # the indexer's worker processes start through this binary
    sys.exit(main())
