"""Versioned wire contract for the replacement computer implementation."""
from __future__ import annotations

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from typing import Any


class ContractError(ValueError):
    """The wire payload violates the versioned contract."""


@dataclass(frozen=True)
class AudioFormat:
    sample_rate_hz: int
    channels: int
    encoding: str
    frame_duration_ms: int

    @property
    def frame_bytes(self) -> int:
        if self.encoding != "pcm_s16le":
            raise ContractError("unsupported audio encoding")
        return self.sample_rate_hz * self.channels * 2 * self.frame_duration_ms // 1000


@dataclass(frozen=True)
class SessionStart:
    source_lang: str
    target_lang: str
    audio: AudioFormat

    def to_payload(self) -> dict[str, Any]:
        return {
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "audio": {
                "sample_rate_hz": self.audio.sample_rate_hz,
                "channels": self.audio.channels,
                "encoding": self.audio.encoding,
                "frame_duration_ms": self.audio.frame_duration_ms,
            },
        }


@dataclass(frozen=True)
class AudioInput:
    stream_id: str
    seq: int
    capture_time_ms: int
    duration_ms: int
    data: bytes

    @classmethod
    def from_payload(cls, payload: dict[str, Any], audio: AudioFormat) -> "AudioInput":
        try:
            data = base64.b64decode(payload["data_b64"], validate=True)
            frame = cls(
                stream_id=payload["stream_id"],
                seq=payload["seq"],
                capture_time_ms=payload["capture_time_ms"],
                duration_ms=payload["duration_ms"],
                data=data,
            )
        except (KeyError, TypeError, ValueError, binascii.Error) as exc:
            raise ContractError("invalid audio frame") from exc
        if frame.duration_ms != audio.frame_duration_ms:
            raise ContractError("duration does not match negotiated format")
        if len(frame.data) != audio.frame_bytes:
            raise ContractError("frame length does not match negotiated format")
        if not isinstance(frame.seq, int) or frame.seq < 0:
            raise ContractError("sequence must be a non-negative integer")
        return frame


@dataclass(frozen=True)
class Envelope:
    message_type: str
    payload: dict[str, Any]
    session_id: str | None = None
    message_id: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        if not self.message_id:
            object.__setattr__(self, "message_id", str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        result = {
            "v": self.version,
            "type": self.message_type,
            "message_id": self.message_id,
            "payload": self.payload,
        }
        if self.session_id is not None:
            result["session_id"] = self.session_id
        return result


_ALLOWED_TYPES = {"session.start", "session.stop", "session.cancel", "session.resume", "audio.input", "audio.ack", "audio.output", "error"}


def encode_envelope(envelope: Envelope) -> str:
    if envelope.version != 1 or envelope.message_type not in _ALLOWED_TYPES:
        raise ContractError("unsupported envelope")
    return json.dumps(envelope.to_dict(), separators=(",", ":"), sort_keys=True)


def decode_envelope(raw: str) -> Envelope:
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ContractError("malformed JSON") from exc
    if not isinstance(data, dict):
        raise ContractError("envelope must be an object")
    if data.get("v") != 1:
        raise ContractError("unsupported protocol version")
    message_type = data.get("type")
    if message_type not in _ALLOWED_TYPES:
        raise ContractError(f"unknown message type: {message_type}")
    if not isinstance(data.get("message_id"), str) or not data["message_id"]:
        raise ContractError("message_id must be non-empty")
    if not isinstance(data.get("payload"), dict):
        raise ContractError("payload must be an object")
    session_id = data.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        raise ContractError("session_id must be a string")
    return Envelope(
        version=1,
        message_type=message_type,
        message_id=data["message_id"],
        session_id=session_id,
        payload=data["payload"],
    )
