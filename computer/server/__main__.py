"""Run the replacement local server."""
import uvicorn

from computer.server.app import app


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
