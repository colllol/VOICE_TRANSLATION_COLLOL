"""Local WebSocket application for the replacement computer server."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sqlite3
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import anyio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from computer.server.contract import AudioFormat, AudioInput, ContractError
from computer.server.coordinator import Session, SessionCoordinator
from computer.server.pipeline import DuplexPipeline, PipelineError
from computer.server.providers import (
    ProviderConfigError, ProviderError, TranslationProvider, TranslationResult, create_translation_provider,
)
from computer.server.storage import SQLiteStore


AUDIO = AudioFormat(16000, 1, "pcm_s16le", 20)
MAX_MESSAGE_BYTES = 4096
MAX_UTTERANCE_BYTES = 10 * 32000
MAX_OUTPUT_BYTES = 60 * 32000
SEND_TIMEOUT_SECONDS = 5
TRANSLATION_TIMEOUT_SECONDS = 55
MAX_PROVIDER_WORKERS = 4
LOGGER = logging.getLogger(__name__)
Language = Literal["vi", "en", "zh", "ja", "ko", "fr"]


class LanguageSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_lang: Language = "vi"
    target_lang: Language = "en"

    @model_validator(mode="after")
    def require_distinct_languages(self) -> "LanguageSettings":
        if self.source_lang == self.target_lang:
            raise ValueError("source and target languages must differ")
        return self


def _error(code: str, detail: str, request_id: str | None = None) -> dict[str, Any]:
    return {
        "v": 1,
        "type": "error",
        "message_id": request_id or "server-error",
        "payload": {"code": code, "detail": detail},
    }


def create_app(
    database_path: str | Path | None = None, *, grace_seconds: float = 30,
    provider_factory=create_translation_provider,
) -> FastAPI:
    path = Path(database_path or os.getenv("VOICE_TRANSLATION_DB_PATH") or "computer-data.db").expanduser().resolve()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = SQLiteStore(path)
        store.cancel_interrupted_sessions()
        app.state.store = store
        app.state.sessions = SessionTransport(store, grace_seconds, provider_factory)
        try:
            yield
        finally:
            app.state.sessions.shutdown()

    app = FastAPI(title="Voice Translation Computer Server", lifespan=lifespan)



    @app.get("/settings")
    def read_settings() -> LanguageSettings:
        try:
            values = app.state.store.get_languages()
        except sqlite3.Error as exc:
            raise HTTPException(503, "settings unavailable") from exc
        try:
            return LanguageSettings.model_validate(values)
        except ValidationError:
            return LanguageSettings()

    @app.put("/settings")
    def write_settings(settings: LanguageSettings) -> LanguageSettings:
        if settings.model_fields_set != {"source_lang", "target_lang"}:
            raise HTTPException(422, "both languages are required")
        try:
            app.state.store.set_languages(settings.source_lang, settings.target_lang)
        except sqlite3.Error as exc:
            raise HTTPException(503, "settings unavailable") from exc
        return settings

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "voice-translation-computer"}


    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await app.state.sessions.serve(ws)

    return app


class CommandError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


@dataclass
class LiveSession:
    session: Session
    pipeline: DuplexPipeline
    provider: TranslationProvider
    provider_lock: threading.Lock
    cancelled: threading.Event = field(default_factory=threading.Event)
    expiry: asyncio.TimerHandle | None = None
    utterances: dict[str, bytearray] = field(default_factory=dict)
    next_chunk: dict[str, int] = field(default_factory=dict)

    @property
    def provider_name(self) -> str:
        return getattr(self.provider, "capabilities", {}).get("tts", "unknown")


class SessionTransport:
    def __init__(self, store: SQLiteStore, grace_seconds: float, provider_factory) -> None:
        self.store = store
        self.coordinator = SessionCoordinator(grace_seconds)
        self.sessions: dict[str, LiveSession] = {}
        self.provider_factory = provider_factory
        self._provider_jobs: set[asyncio.Future[TranslationResult]] = set()

    async def _run_provider(self, live: LiveSession, audio: bytes, source: str, target: str) -> TranslationResult:
        if len(self._provider_jobs) >= MAX_PROVIDER_WORKERS:
            raise CommandError("provider_busy", "translation capacity exhausted")
        job = asyncio.get_running_loop().run_in_executor(None, _translate, live, audio, source, target)
        self._provider_jobs.add(job)

        def completed(result: asyncio.Future[TranslationResult]) -> None:
            self._provider_jobs.discard(result)
            if not result.cancelled():
                result.exception()  # The WebSocket waiter may have already been cancelled.

        job.add_done_callback(completed)
        return await asyncio.shield(job)

    def _record(self, session: Session) -> None:
        self.store.record_session(
            session.session_id, session.source_lang, session.target_lang, session.state.value
        )

    def _release(self, session_id: str) -> None:
        live = self.sessions.pop(session_id, None)
        if live:
            live.cancelled.set()
            if live.expiry:
                live.expiry.cancel()
            live.pipeline.cancel()
        self.coordinator.forget(session_id)

    def _cancel(self, session_id: str) -> None:
        self.coordinator.cancel(session_id)
        self.sessions[session_id].cancelled.set()
        try:
            self._record(self.coordinator.get(session_id))
        finally:
            self._release(session_id)

    def _expire(self, session_id: str) -> None:
        try:
            self._cancel(session_id)
        except sqlite3.Error:
            LOGGER.exception("Could not persist session cancellation")

    def shutdown(self) -> None:
        for session_id in list(self.sessions):
            self._expire(session_id)

    def _disconnect(self, session_id: str) -> None:
        self.coordinator.disconnect(session_id)
        live = self.sessions[session_id]
        live.utterances.clear()
        try:
            self._record(live.session)
        except sqlite3.Error:
            LOGGER.exception("Could not persist session disconnect")
            self._expire(session_id)
            return
        live.expiry = asyncio.get_running_loop().call_later(
            self.coordinator.grace_seconds, self._expire, session_id
        )

    def _start(self, payload: dict[str, Any]) -> Session:
        languages = LanguageSettings.model_validate({
            "source_lang": payload.get("source_lang"), "target_lang": payload.get("target_lang")
        })
        if "audio" in payload and payload["audio"] != asdict(AUDIO):
            raise ContractError("unsupported audio format")
        session = self.coordinator.start(languages.source_lang, languages.target_lang)
        try:
            provider = self.provider_factory()
            self.sessions[session.session_id] = LiveSession(
                session, DuplexPipeline(AUDIO), provider, threading.Lock()
            )
            self._record(session)
        except Exception:
            self._release(session.session_id)
            raise
        return session

    def _resume(self, session_id: str | None, payload: dict[str, Any]) -> Session:
        token = payload.get("resume_token")
        if not session_id or not isinstance(token, str) or not token.isascii():
            raise CommandError("resume_rejected", "session cannot be resumed")
        try:
            session = self.coordinator.resume(session_id, token)
        except ValueError as exc:
            raise CommandError("resume_rejected", "session cannot be resumed") from exc
        live = self.sessions[session_id]
        if live.expiry:
            live.expiry.cancel()
            live.expiry = None
        try:
            self._record(session)
        except sqlite3.Error:
            self._expire(session_id)
            raise
        return session

    async def _utterance(self, live: LiveSession, command: str, payload: dict[str, Any]):
        stream = payload.get("stream_id")
        if stream not in ("a2b", "b2a"):
            raise ContractError("unknown stream")
        if command == "utterance.chunk":
            seq = payload.get("seq")
            if type(seq) is not int or seq != live.next_chunk.get(stream, 0):
                raise ContractError("unexpected chunk sequence")
            frame = AudioInput.from_payload({**payload, "duration_ms": 20, "capture_time_ms": 0}, AUDIO)
            buf = live.utterances.setdefault(stream, bytearray())
            if len(buf) + len(frame.data) > MAX_UTTERANCE_BYTES:
                raise ContractError("utterance too long")
            buf.extend(frame.data)
            live.next_chunk[stream] = seq + 1
            return "utterance.ack", {"stream_id": stream, "seq": seq}
        audio = live.utterances.pop(stream, None)
        if not audio:
            raise ContractError("no buffered utterance")
        source, target = live.session.source_lang, live.session.target_lang
        if stream == "b2a":
            source, target = target, source
        try:
            result = await self._run_provider(live, bytes(audio), source, target)
        except ProviderError as exc:
            raise CommandError("provider_unavailable", "translation provider unavailable") from exc
        if not 0 < len(result.audio) <= MAX_OUTPUT_BYTES or len(result.audio) % 2:
            raise CommandError("invalid_output", "provider returned invalid PCM")
        return "utterance.output", {"stream_id": stream, "data_b64": base64.b64encode(result.audio).decode("ascii")}

    async def _audio(self, live: LiveSession, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("stream_id") not in ("a2b", "b2a"):
            raise ContractError("unknown stream")
        if type(payload.get("seq")) is not int:
            raise ContractError("sequence must be an integer")
        capture_time = payload.get("capture_time_ms")
        if type(capture_time) is not int or capture_time < 0:
            raise ContractError("capture time must be a non-negative integer")
        if type(payload.get("duration_ms")) is not int:
            raise ContractError("duration must be an integer")
        frame = AudioInput.from_payload(payload, AUDIO)
        session = live.session
        source, target = session.source_lang, session.target_lang
        if frame.stream_id == "b2a":
            source, target = target, source
        try:
            translated = await self._run_provider(live, frame.data, source, target)
        except ProviderError as exc:
            LOGGER.warning("Translation provider rejected utterance: %s", exc)
            raise CommandError("provider_unavailable", "translation provider unavailable") from exc
        data = translated.audio[:AUDIO.frame_bytes].ljust(AUDIO.frame_bytes, b"\0")
        return asdict(live.pipeline.process(replace(frame, data=data)))

    async def _dispatch(self, message: dict[str, Any], owned: str | None) -> tuple[str | None, dict[str, Any]]:
        command, payload = message["type"], message["payload"]
        session_id = message.get("session_id")
        if command in ("session.start", "session.resume"):
            if owned is not None:
                raise CommandError("session_already_active", "connection already owns a session")
            if command == "session.start":
                session, response_type = self._start(payload), "session.started"
            else:
                session, response_type = self._resume(session_id, payload), "session.resumed"
            owned = session_id = session.session_id
            live = self.sessions[owned]
            result = {"audio": asdict(AUDIO), "resume_token": session.resume_token,
                      "utterance_audio": "chunks-v1", "provider": live.provider_name,
                      "next_chunk": live.next_chunk}
        elif not owned or session_id != owned:
            raise CommandError("session_not_active", "session is not owned by this connection")
        elif command == "session.cancel":
            self._cancel(owned)
            owned, response_type, result = None, "session.cancelled", {}
        elif command == "audio.input":
            if self.sessions[owned].provider_name == "azure":
                raise CommandError("utterance_required", "Azure requires utterance chunks")
            response_type, result = "audio.output", await self._audio(self.sessions[owned], payload)
        elif command in ("utterance.chunk", "utterance.finish"):
            response_type, result = await self._utterance(self.sessions[owned], command, payload)
        else:
            raise ContractError("unsupported command")
        return owned, {
            "v": 1, "type": response_type, "message_id": message["message_id"],
            "session_id": session_id, "payload": result,
        }

    async def _respond(self, message: dict[str, Any], owned: str | None):
        request_id = message["message_id"]
        try:
            return await self._dispatch(message, owned)
        except CommandError as exc:
            response = _error(exc.code, str(exc), request_id)
        except (ProviderConfigError, OSError):
            LOGGER.warning("Translation provider request failed")
            response = _error("provider_unavailable", "translation provider unavailable", request_id)
        except ValidationError:
            response = _error("invalid_message", "invalid language pair", request_id)
        except (ContractError, PipelineError) as exc:
            response = _error("invalid_message", str(exc), request_id)
        except sqlite3.Error:
            LOGGER.exception("Could not persist session state")
            response = _error("storage_unavailable", "session storage unavailable", request_id)
        return owned if owned in self.sessions else None, response

    async def serve(self, ws: WebSocket) -> None:
        if "origin" in ws.headers:
            await ws.close(code=1008)
            return
        await ws.accept()
        owned: str | None = None
        incoming = asyncio.create_task(ws.receive())
        pending = None
        pending_id = None
        try:
            while True:
                await asyncio.wait({incoming, pending} if pending else {incoming},
                                   return_when=asyncio.FIRST_COMPLETED)
                message = None
                response = None
                if incoming.done():
                    event = incoming.result()
                    if event["type"] == "websocket.disconnect":
                        return
                    incoming = asyncio.create_task(ws.receive())
                    try:
                        message = _parse_message(event.get("text"))
                    except ContractError as exc:
                        response = _error("invalid_message", str(exc))
                cancels_owned = (message is not None and owned is not None
                                 and message["type"] == "session.cancel"
                                 and message.get("session_id") == owned)
                # A completed result is still revocable until sent. If cancel and
                # output are both ready, retire the session without sending audio.
                if pending and pending.done() and not cancels_owned:
                    try:
                        owned, completed = pending.result()
                    except TimeoutError:
                        if owned is not None:
                            self._expire(owned)
                            owned = None
                        completed = _error("translation_timeout", "translation timed out", pending_id)
                    pending = None
                    await asyncio.wait_for(ws.send_json(completed), SEND_TIMEOUT_SECONDS)
                if message is not None:
                    command = message["type"]
                    request_id = message["message_id"]
                    if pending and command != "session.cancel":
                        response = _error("translation_busy", "translation in progress", request_id)
                    elif command in ("utterance.finish", "audio.input"):
                        pending_id = request_id
                        pending = asyncio.create_task(asyncio.wait_for(
                            self._respond(message, owned), TRANSLATION_TIMEOUT_SECONDS,
                        ))
                    else:
                        owned, response = await self._respond(message, owned)
                        if pending and owned is None:
                            pending.cancel()
                            await asyncio.gather(pending, return_exceptions=True)
                            pending = None
                if response is not None:
                    await asyncio.wait_for(ws.send_json(response), SEND_TIMEOUT_SECONDS)
        except TimeoutError:
            if owned is not None:
                self._expire(owned)
                owned = None
            try:
                await asyncio.wait_for(ws.close(code=1013), SEND_TIMEOUT_SECONDS)
            except (WebSocketDisconnect, OSError):
                pass
        except (WebSocketDisconnect, OSError):
            pass
        finally:
            if owned is not None and owned in self.sessions:
                if pending:
                    self._expire(owned)
                else:
                    self._disconnect(owned)
            tasks = [incoming] if pending is None else [incoming, pending]
            for task in tasks:
                task.cancel()
            # ASGI hosts may already have cancelled the enclosing scope.
            with anyio.CancelScope(shield=True):
                await asyncio.gather(*tasks, return_exceptions=True)


def _parse_message(text: str | None) -> dict[str, Any]:
    if text is None:
        raise ContractError("expected a text message")
    if len(text) > MAX_MESSAGE_BYTES or len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ContractError("message too large")
    try:
        message = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise ContractError("malformed JSON") from exc
    if not isinstance(message, dict) or type(message.get("v")) is not int or message["v"] != 1:
        raise ContractError("invalid envelope or unsupported version")
    if not isinstance(message.get("message_id"), str) or not message["message_id"].strip():
        raise ContractError("message_id must be non-empty")
    if not isinstance(message.get("type"), str) or not isinstance(message.get("payload"), dict):
        raise ContractError("invalid envelope")
    if message.get("session_id") is not None and not isinstance(message["session_id"], str):
        raise ContractError("session_id must be a string")
    return message


app = create_app()


def _translate(live: LiveSession, audio: bytes, source: str, target: str) -> TranslationResult:
    with live.provider_lock:
        if live.cancelled.is_set():
            raise ProviderError("translation cancelled")
        translate_cancellable = getattr(live.provider, "translate_cancellable", None)
        if translate_cancellable is not None:
            return translate_cancellable(audio, source, target, live.cancelled.is_set)
        return live.provider.translate(audio, source, target)
