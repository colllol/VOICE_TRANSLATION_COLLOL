"""Message validation for transport contract enforcement."""
from __future__ import annotations

import math
from typing import Any

from protocol.messages import (
    AudioChunk,
    CancelSession,
    Direction,
    ErrorCode,
    ErrorMessage,
    ResumeSession,
    SessionEnd,
    SessionStart,
)


class ValidationError(ValueError):
    """Message validation failed."""


class MessageValidator:
    """Validates transport messages against VT-002 contract."""

    @staticmethod
    def validate_session_start(msg: Any) -> str | None:
        if not isinstance(msg, SessionStart):
            return "must be SessionStart instance"
        if not isinstance(msg.session_id, str) or not msg.session_id.strip():
            return "session_id must be non-empty string"
        if not isinstance(msg.source_lang, str) or not msg.source_lang.strip():
            return "source_lang must be non-empty string"
        if not isinstance(msg.target_lang, str) or not msg.target_lang.strip():
            return "target_lang must be non-empty string"
        if isinstance(msg.timestamp_ms, bool) or not isinstance(msg.timestamp_ms, (int, float)):
            return "timestamp_ms must be a number"
        if not math.isfinite(msg.timestamp_ms) or msg.timestamp_ms < 0:
            return "timestamp_ms must be finite and non-negative"
        if not isinstance(msg.max_queue_size, int) or msg.max_queue_size <= 0:
            return "max_queue_size must be positive integer"
        return None

    @staticmethod
    def validate_audio_chunk(msg: Any) -> str | None:
        if not isinstance(msg, AudioChunk):
            return "must be AudioChunk instance"
        if not isinstance(msg.session_id, str) or not msg.session_id.strip():
            return "session_id must be non-empty string"
        if not isinstance(msg.direction, Direction):
            return "direction must be Direction enum"
        if not isinstance(msg.seq, int) or isinstance(msg.seq, bool) or msg.seq < 0:
            return "seq must be non-negative integer"
        if isinstance(msg.timestamp_ms, bool) or not isinstance(msg.timestamp_ms, (int, float)):
            return "timestamp_ms must be a number"
        if not math.isfinite(msg.timestamp_ms) or msg.timestamp_ms < 0:
            return "timestamp_ms must be finite and non-negative"
        if not isinstance(msg.payload, bytes):
            return "payload must be bytes"
        if not isinstance(msg.is_final, bool):
            return "is_final must be boolean"
        return None

    @staticmethod
    def validate_session_end(msg: Any) -> str | None:
        if not isinstance(msg, SessionEnd):
            return "must be SessionEnd instance"
        if not isinstance(msg.session_id, str) or not msg.session_id.strip():
            return "session_id must be non-empty string"
        if isinstance(msg.timestamp_ms, bool) or not isinstance(msg.timestamp_ms, (int, float)):
            return "timestamp_ms must be a number"
        if not math.isfinite(msg.timestamp_ms) or msg.timestamp_ms < 0:
            return "timestamp_ms must be finite and non-negative"
        if msg.reason not in ("completed", "cancelled"):
            return 'reason must be "completed" or "cancelled"'
        return None

    @staticmethod
    def validate_error_message(msg: Any) -> str | None:
        if not isinstance(msg, ErrorMessage):
            return "must be ErrorMessage instance"
        if not isinstance(msg.session_id, str) or not msg.session_id.strip():
            return "session_id must be non-empty string"
        if isinstance(msg.timestamp_ms, bool) or not isinstance(msg.timestamp_ms, (int, float)):
            return "timestamp_ms must be a number"
        if not math.isfinite(msg.timestamp_ms) or msg.timestamp_ms < 0:
            return "timestamp_ms must be finite and non-negative"
        if not isinstance(msg.code, ErrorCode):
            return "code must be ErrorCode enum"
        if not isinstance(msg.detail, str):
            return "detail must be string"
        return None

    @staticmethod
    def validate_cancel_session(msg: Any) -> str | None:
        if not isinstance(msg, CancelSession):
            return "must be CancelSession instance"
        if not isinstance(msg.session_id, str) or not msg.session_id.strip():
            return "session_id must be non-empty string"
        if isinstance(msg.timestamp_ms, bool) or not isinstance(msg.timestamp_ms, (int, float)):
            return "timestamp_ms must be a number"
        if not math.isfinite(msg.timestamp_ms) or msg.timestamp_ms < 0:
            return "timestamp_ms must be finite and non-negative"
        return None

    @staticmethod
    def validate_resume_session(msg: Any) -> str | None:
        if not isinstance(msg, ResumeSession):
            return "must be ResumeSession instance"
        if not isinstance(msg.session_id, str) or not msg.session_id.strip():
            return "session_id must be non-empty string"
        if isinstance(msg.timestamp_ms, bool) or not isinstance(msg.timestamp_ms, (int, float)):
            return "timestamp_ms must be a number"
        if not math.isfinite(msg.timestamp_ms) or msg.timestamp_ms < 0:
            return "timestamp_ms must be finite and non-negative"
        if not isinstance(msg.last_seq_a2b, int) or msg.last_seq_a2b < -1:
            return "last_seq_a2b must be >= -1"
        if not isinstance(msg.last_seq_b2a, int) or msg.last_seq_b2a < -1:
            return "last_seq_b2a must be >= -1"
        return None