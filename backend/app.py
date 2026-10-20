"""FastAPI WebSocket transport for session service."""
from __future__ import annotations

import base64
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
    app.state.session_service = service

    @app.get("/health")
    def health():
        return JSONResponse(health_payload())

    @app.websocket("/ws/session")
    async def session_websocket(websocket: WebSocket):
        await websocket.accept()
        owned_sessions: set[str] = set()
        try:
            while True:
                raw_msg = await websocket.receive_text()
                try:
                    envelope = json.loads(raw_msg)
                except json.JSONDecodeError:
                    await _send_error(websocket, "unknown", "malformed JSON")
                    continue

                if not isinstance(envelope, dict):
                    await _send_error(websocket, "unknown", "envelope must be JSON object")
                    continue

                msg_type = envelope.get("type")
                if not msg_type:
                    await _send_error(websocket, "unknown", "missing type field")
                    continue

                payload = envelope.get("payload")
                if payload is None:
                    await _send_error(websocket, "unknown", "missing payload field")
                    continue

                if not isinstance(payload, dict):
                    await _send_error(websocket, "unknown", "payload must be JSON object")
                    continue

                handler = _HANDLERS.get(msg_type)
                if not handler:
                    await _send_error(websocket, "unknown", f"unknown type: {msg_type}")
                    continue

                await handler(websocket, service, payload, owned_sessions)

        except WebSocketDisconnect:
            pass
        finally:
            # Cancel only sessions started by this WebSocket
            for session_id in list(owned_sessions):
                service.disconnect_session(session_id, time.time() * 1000)

    return app


async def _handle_session_start(ws: WebSocket, svc: SessionService, payload: dict[str, Any], owned_sessions: set[str]):
    try:
        msg = SessionStart(**payload)
    except (TypeError, ValueError) as e:
        await _send_error(ws, payload.get("session_id", "unknown"), f"SessionStart parse: {e}")
        return

    err = svc.start_session(msg)
    if err:
        await _send_error_message(ws, err)
    else:
        owned_sessions.add(msg.session_id)
        await ws.send_json({"type": "session_started", "session_id": msg.session_id})


async def _handle_audio_chunk(ws: WebSocket, svc: SessionService, payload: dict[str, Any], owned_sessions: set[str]):
    session_id = payload.get("session_id", "unknown")

    # Required base64-encoded payload
    payload_b64 = payload.get("payload_b64")
    if not isinstance(payload_b64, str):
        await _send_error(ws, session_id, "payload_b64 must be a string")
        return

    try:
        payload_bytes = base64.b64decode(payload_b64, validate=True)
    except Exception:
        await _send_error(ws, session_id, "invalid base64 in payload_b64")
        return

    # Build AudioChunk message without mutating original payload
    try:
        direction_raw = payload.get("direction")
        direction = Direction(direction_raw) if isinstance(direction_raw, str) else direction_raw

        msg = AudioChunk(
            session_id=payload.get("session_id"),
            direction=direction,
            seq=payload.get("seq"),
            timestamp_ms=payload.get("timestamp_ms"),
            payload=payload_bytes,
            is_final=payload.get("is_final", False)
        )
    except (TypeError, ValueError) as e:
        await _send_error(ws, session_id, f"AudioChunk parse: {e}")
        return

    err = svc.process_audio_chunk(msg)
    if err:
        await _send_error_message(ws, err)
    else:
        await ws.send_json({
            "type": "audio_chunk_accepted",
            "session_id": msg.session_id,
            "direction": msg.direction.value,
            "seq": msg.seq,
        })


async def _handle_session_end(ws: WebSocket, svc: SessionService, payload: dict[str, Any], owned_sessions: set[str]):
    try:
        msg = SessionEnd(**payload)
    except (TypeError, ValueError) as e:
        await _send_error(ws, payload.get("session_id", "unknown"), f"SessionEnd parse: {e}")
        return

    err = svc.end_session(msg)
    if err:
        await _send_error_message(ws, err)
    else:
        owned_sessions.discard(msg.session_id)
        await ws.send_json({"type": "session_ended", "session_id": msg.session_id})


async def _handle_cancel_session(ws: WebSocket, svc: SessionService, payload: dict[str, Any], owned_sessions: set[str]):
    try:
        msg = CancelSession(**payload)
    except (TypeError, ValueError) as e:
        await _send_error(ws, payload.get("session_id", "unknown"), f"CancelSession parse: {e}")
        return

    err = svc.cancel_session(msg)
    if err:
        await _send_error_message(ws, err)
    else:
        owned_sessions.discard(msg.session_id)
        await ws.send_json({"type": "session_cancelled", "session_id": msg.session_id})


async def _handle_resume_session(ws: WebSocket, svc: SessionService, payload: dict[str, Any], owned_sessions: set[str]):
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
