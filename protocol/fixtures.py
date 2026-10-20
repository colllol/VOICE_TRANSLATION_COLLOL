"""Test fixtures for protocol messages."""
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


def valid_session_start(session_id: str = "sess-001") -> SessionStart:
    return SessionStart(
        session_id=session_id,
        timestamp_ms=1000.0,
        source_lang="vi",
        target_lang="en",
        max_queue_size=50,
    )


def valid_audio_chunk(
    session_id: str = "sess-001",
    direction: Direction = Direction.A_TO_B,
    seq: int = 0,
) -> AudioChunk:
    return AudioChunk(
        session_id=session_id,
        direction=direction,
        seq=seq,
        timestamp_ms=1100.0 + seq * 10,
        payload=b"\x00\x01" * 160,
        is_final=False,
    )


def valid_session_end(session_id: str = "sess-001") -> SessionEnd:
    return SessionEnd(
        session_id=session_id,
        timestamp_ms=2000.0,
        reason="completed",
    )


def valid_error_message(session_id: str = "sess-001") -> ErrorMessage:
    return ErrorMessage(
        session_id=session_id,
        timestamp_ms=1500.0,
        code=ErrorCode.INTERNAL_ERROR,
        detail="test error",
    )


def valid_cancel_session(session_id: str = "sess-001") -> CancelSession:
    return CancelSession(
        session_id=session_id,
        timestamp_ms=1800.0,
    )


def valid_resume_session(session_id: str = "sess-001") -> ResumeSession:
    return ResumeSession(
        session_id=session_id,
        timestamp_ms=2500.0,
        last_seq_a2b=42,
        last_seq_b2a=38,
    )
