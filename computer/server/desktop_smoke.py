"""Run desktop contract tests against a local server and a temporary SQLite database."""
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
from urllib.request import urlopen

import uvicorn

from computer.server.app import create_app


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    wrapper = root / "computer-desktop" / ("gradlew.bat" if os.name == "nt" else "gradlew")
    with tempfile.TemporaryDirectory() as directory, socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        app = create_app(database_path=str(Path(directory) / "smoke.db"))
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 6
            while True:
                try:
                    with urlopen(url + "/health", timeout=0.4) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Temporary backend did not start")
                time.sleep(0.1)
            subprocess.run(
                [str(wrapper), "test", "--rerun-tasks", "--console=plain"],
                cwd=wrapper.parent, env={**os.environ, "VOICE_DESKTOP_TEST_URL": url}, check=True,
            )
        finally:
            server.should_exit = True
            thread.join(timeout=10)


if __name__ == "__main__":
    main()
