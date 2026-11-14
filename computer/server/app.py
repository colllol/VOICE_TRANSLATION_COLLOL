"""Local WebSocket application for the replacement computer server."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from computer.server.contract import AudioFormat, AudioInput, ContractError
from computer.server.coordinator import SessionCoordinator, SessionState
from computer.server.pipeline import DuplexPipeline
from computer.server.providers import FakeTranslationProvider


AUDIO = AudioFormat(16000, 1, "pcm_s16le", 20)


def _error(code: str, detail: str, request_id: str | None = None) -> dict[str, Any]:
    return {
        "v": 1,
        "type": "error",
        "message_id": request_id or "server-error",
        "payload": {"code": code, "detail": detail},
    }


def create_app() -> FastAPI:
    app = FastAPI(title="Voice Translation Computer Server")
    coordinator = SessionCoordinator()
    pipelines: dict[str, DuplexPipeline] = {}
    providers: dict[str, FakeTranslationProvider] = {}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "voice-translation-computer"}

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        owned_session_id: str | None = None
        try:
            while True:
                message = await ws.receive_json()
                message_id = message.get("message_id")
                message_type = message.get("type")
                payload = message.get("payload")
                if message.get("v") != 1 or not isinstance(payload, dict):
                    await ws.send_json(_error("invalid_message", "invalid envelope", message_id))
                    continue

                if message_type == "session.start":
                    session = coordinator.start(
                        payload.get("source_lang", ""), payload.get("target_lang", "")
                    )
                    owned_session_id = session.session_id
                    pipelines[session.session_id] = DuplexPipeline(AUDIO)
                    providers[session.session_id] = FakeTranslationProvider()
                    await ws.send_json({
                        "v": 1,
                        "type": "session.started",
                        "message_id": message_id,
                        "session_id": session.session_id,
                        "payload": {
                            "audio": {
                                "sample_rate_hz": AUDIO.sample_rate_hz,
                                "channels": AUDIO.channels,
                                "encoding": AUDIO.encoding,
                                "frame_duration_ms": AUDIO.frame_duration_ms,
                            }
                        },
                    })
                    continue

                if not owned_session_id or message.get("session_id") != owned_session_id:
                    await ws.send_json(_error("session_not_active", "session is not owned by this connection", message_id))
                    continue
                session = coordinator.get(owned_session_id)

                if message_type == "session.cancel":
                    coordinator.cancel(owned_session_id)
                    pipelines[owned_session_id].cancel()
                    await ws.send_json({"v": 1, "type": "session.cancelled", "message_id": message_id, "session_id": owned_session_id, "payload": {}})
                elif message_type == "audio.input":
                    if session.state is not SessionState.ACTIVE:
                        await ws.send_json(_error("session_not_active", "session is not active", message_id))
                        continue
                    frame = AudioInput.from_payload(payload, AUDIO)
                    translated = providers[owned_session_id].translate(
                        frame.data, session.source_lang, session.target_lang
                    )
                    output = pipelines[owned_session_id].process(
                        AudioInput(
                            frame.stream_id,
                            frame.seq,
                            frame.capture_time_ms,
                            frame.duration_ms,
                            translated.audio[: AUDIO.frame_bytes].ljust(AUDIO.frame_bytes, b"\0"),
                        )
                    )
                    await ws.send_json({
                        "v": 1,
                        "type": "audio.output",
                        "message_id": message_id,
                        "session_id": owned_session_id,
                        "payload": {
                            "stream_id": output.stream_id,
                            "input_seq_start": output.input_seq_start,
                            "input_seq_end": output.input_seq_end,
                            "output_seq": output.output_seq,
                            "duration_ms": output.duration_ms,
                            "data_b64": output.data_b64,
                        },
                    })
                else:
                    await ws.send_json(_error("invalid_message", "unsupported command", message_id))
        except WebSocketDisconnect:
            if owned_session_id:
                coordinator.disconnect(owned_session_id)
        except (ContractError, ValueError) as exc:
            await ws.send_json(_error("invalid_message", str(exc)))
        except Exception as exc:
            await ws.send_json(_error("pipeline_error", str(exc)))

    return app


app = create_app()
