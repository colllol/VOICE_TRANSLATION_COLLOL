"""Run the replacement local server."""
import os
import sys
from threading import Thread

import uvicorn

from computer.server.app import MAX_MESSAGE_BYTES, app


if __name__ == "__main__":
    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=int(os.getenv("VOICE_TRANSLATION_PORT", "8765")), ws="websockets",
        ws_max_size=MAX_MESSAGE_BYTES, ws_max_queue=4,
        timeout_graceful_shutdown=3,
    ))
    if "--desktop-child" in sys.argv:
        def stop_on_parent_close():
            # The private stdin pipe closes when the owning desktop exits.
            sys.stdin.buffer.read(1)
            server.should_exit = True

        Thread(target=stop_on_parent_close, daemon=True).start()
    server.run()
