"""FastAPI WebSocket transport for session service."""
from __future__ import annotations

import json
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from backend.health import health_payload
from backend.session import SessionService
from protocol.messages import (
    AudioChunk,
    CancelSession,
    Direction,
    ErrorMessage,
    ResumeSession,
    SessionEnd,
    SessionStart,
)


def create_app() -> FastAPI:
    app = FastAPI(title="Voice Translation Backend")
    service = SessionService()

    @app.get("/health")
    def health():
        return JSONResponse(health_payload())

    @app.websocket("/ws/session")
    async def session_websocket(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                raw_msg = await websocket.receive_text()
                try:
                    envelope = json.loads(raw_msg)
                except json.JSONDecodeError:
                    await _send_error(websocket, "unknown", "malformed JSON")
                    continue

                msg_type = envelope.get("type")
                if not msg_type:
                    await _send_error(websocket, "unknown", "missing type field")
                    continue

                payload = envelope.get("payload")
                if payload is None:
                    await _send_error(websocket, "unknown", "missing payload field")
                    continue

                handler = _HANDLERS.get(msg_type)
                if not handler:
                    await _send_error(websocket, "unknown", f"unknown type: {msg_type}")
                    continue

                await handler(websocket, service, payload)

        except WebSocketDisconnect:
            pass

    return app


async def _handle_session_start(ws: WebSocket, svc: SessionService, payload: dict[str, Any]):
    try:
        msg = SessionStart(**payload)
    except (TypeError, ValueError) as e:
        await _send_error(ws, payload.get("session_id", "unknown"), f"SessionStart parse: {e}")
        return

    err = svc.start_session(msg)
    if err:
        await _send_error_message(ws, err)
    else:
        await ws.send_json({"type": "session_started", "session_id": msg.session_id})


async def _handle_audio_chunk(ws: WebSocket, svc: SessionService, payload: dict[str, Any]):
    try:
        direction_raw = payload.get("direction")
        if isinstance(direction_raw, str):
            payload["direction"] = Direction(direction_raw)

        # ponytail: convert string payload to bytes for JSON transport
        payload_raw = payload.get("payload")
        if isinstance(payload_raw, str):
            payload["payload"] = payload_raw.encode("utf-8")

        msg = AudioChunk(**payload)
    except (TypeError, ValueError) as e:
        await _send_error(ws, payload.get("session_id", "unknown"), f"AudioChunk parse: {e}")
        return

    err = svc.process_audio_chunk(msg)
    if err:
        await _send_error_message(ws, err)


async def _handle_session_end(ws: WebSocket, svc: SessionService, payload: dict[str, Any]):
    try:
        msg = SessionEnd(**payload)
    except (TypeError, ValueError) as e:
        await _send_error(ws, payload.get("session_id", "unknown"), f"SessionEnd parse: {e}")
        return

    err = svc.end_session(msg)
    if err:
        await _send_error_message(ws, err)
    else:
        await ws.send_json({"type": "session_ended", "session_id": msg.session_id})


async def _handle_cancel_session(ws: WebSocket, svc: SessionService, payload: dict[str, Any]):
    try:
        msg = CancelSession(**payload)
    except (TypeError, ValueError) as e:
        await _send_error(ws, payload.get("session_id", "unknown"), f"CancelSession parse: {e}")
        return

    err = svc.cancel_session(msg)
    if err:
        await _send_error_message(ws, err)
    else:
        await ws.send_json({"type": "session_cancelled", "session_id": msg.session_id})


async def _handle_resume_session(ws: WebSocket, svc: SessionService, payload: dict[str, Any]):
    try:
        msg = ResumeSession(**payload)
    except (TypeError, ValueError) as e:
        await _send_error(ws, payload.get("session_id", "unknown"), f"ResumeSession parse: {e}")
        return

    err = svc.resume_session(msg)
    if err:
        await _send_error_message(ws, err)
    else:
        await ws.send_json({"type": "session_resumed", "session_id": msg.session_id})


async def _send_error_message(ws: WebSocket, err: ErrorMessage):
    await ws.send_json({
        "type": "error",
        "session_id": err.session_id,
        "timestamp_ms": err.timestamp_ms,
        "code": err.code.value,
        "detail": err.detail,
    })


async def _send_error(ws: WebSocket, session_id: str, detail: str):
    await ws.send_json({
        "type": "error",
        "session_id": session_id,
        "timestamp_ms": time.time() * 1000,
        "code": "invalid_message",
        "detail": detail,
    })


_HANDLERS = {
    "session_start": _handle_session_start,
    "audio_chunk": _handle_audio_chunk,
    "session_end": _handle_session_end,
    "cancel_session": _handle_cancel_session,
    "resume_session": _handle_resume_session,
}
