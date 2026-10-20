"""Transport message types for session and audio streaming."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class Direction(str, Enum):
    """Audio direction for bidirectional translation."""
    A_TO_B = "a2b"
    B_TO_A = "b2a"


class SessionState(str, Enum):
    """Session lifecycle states."""
    IDLE = "idle"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    ERROR = "error"


class ErrorCode(str, Enum):
    """Failure codes for session/transport errors."""
    INVALID_MESSAGE = "invalid_message"
    STALE_SEQUENCE = "stale_sequence"
    DUPLICATE_SEQUENCE = "duplicate_sequence"
    SESSION_NOT_ACTIVE = "session_not_active"
    BACKPRESSURE_EXCEEDED = "backpressure_exceeded"
    TIMEOUT = "timeout"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class SessionStart:
    """Start a new translation session."""
    session_id: str
    timestamp_ms: float
    source_lang: str
    target_lang: str
    # ponytail: assumes lang codes match ASR/NMT; validation deferred to backend
    max_queue_size: int = 100  # backpressure bound


@dataclass(frozen=True)
class AudioChunk:
    """Bidirectional audio frame with monotonic sequence and timestamp."""
    session_id: str
    direction: Direction
    seq: int  # monotonic per direction, starts at 0
    timestamp_ms: float
    payload: bytes  # PCM audio
    is_final: bool = False  # last chunk before SessionEnd


@dataclass(frozen=True)
class SessionEnd:
    """End session normally."""
    session_id: str
    timestamp_ms: float
    reason: Literal["completed", "cancelled"] = "completed"


@dataclass(frozen=True)
class ErrorMessage:
    """Transport or processing error."""
    session_id: str
    timestamp_ms: float
    code: ErrorCode
    detail: str


@dataclass(frozen=True)
class CancelSession:
    """Cancel active session; clears queues and sequence state."""
    session_id: str
    timestamp_ms: float


@dataclass(frozen=True)
class ResumeSession:
    """Resume session after reconnect; client sends last received seq per direction."""
    session_id: str
    timestamp_ms: float
    last_seq_a2b: int
    last_seq_b2a: int
