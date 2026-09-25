import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("web.backend.app:app", host="127.0.0.1",
                port=int(os.environ.get("VIBECUT_PORT", 8765)), log_level="warning")
