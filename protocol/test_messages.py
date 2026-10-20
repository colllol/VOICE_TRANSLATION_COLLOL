"""Tests for protocol message validation."""
from protocol.validation import MessageValidator
from protocol.messages import (
    AudioChunk,
    Direction,
    ErrorCode,
    ErrorMessage,
    SessionEnd,
    SessionStart,
    CancelSession,
    ResumeSession,
)
from protocol.fixtures import (
    valid_session_start,
    valid_audio_chunk,
    valid_session_end,
    valid_error_message,
    valid_cancel_session,
    valid_resume_session,
)


def test_session_start_valid():
    msg = valid_session_start()
    assert MessageValidator.validate_session_start(msg) is None


def test_session_start_missing_session_id():
    msg = SessionStart(
        session_id="",
        timestamp_ms=1000.0,
        source_lang="vi",
        target_lang="en",
    )
    error = MessageValidator.validate_session_start(msg)
    assert error is not None and "session_id" in error


def test_session_start_invalid_max_queue_size():
    msg = SessionStart(
        session_id="sess-001",
        timestamp_ms=1000.0,
        source_lang="vi",
        target_lang="en",
        max_queue_size=0,
    )
    error = MessageValidator.validate_session_start(msg)
    assert error is not None and "max_queue_size" in error


def test_audio_chunk_valid():
    msg = valid_audio_chunk()
    assert MessageValidator.validate_audio_chunk(msg) is None


def test_audio_chunk_invalid_sequence():
    msg = AudioChunk(
        session_id="sess-001",
        direction=Direction.A_TO_B,
        seq=-1,
        timestamp_ms=1100.0,
        payload=b"\x00\x01" * 160,
    )
    error = MessageValidator.validate_audio_chunk(msg)
    assert error is not None and "seq" in error


def test_audio_chunk_invalid_payload():
    msg = AudioChunk(
        session_id="sess-001",
        direction=Direction.A_TO_B,
        seq=0,
        timestamp_ms=1100.0,
        payload="not bytes",
    )
    error = MessageValidator.validate_audio_chunk(msg)
    assert error is not None and "payload" in error


def test_session_end_valid():
    msg = valid_session_end()
    assert MessageValidator.validate_session_end(msg) is None


def test_session_end_invalid_reason():
    msg = SessionEnd(
        session_id="sess-001",
        timestamp_ms=2000.0,
        reason="invalid_reason",
    )
    error = MessageValidator.validate_session_end(msg)
    assert error is not None and "reason" in error


def test_error_message_valid():
    msg = valid_error_message()
    assert MessageValidator.validate_error_message(msg) is None


def test_cancel_session_valid():
    msg = valid_cancel_session()
    assert MessageValidator.validate_cancel_session(msg) is None


def test_resume_session_valid():
    msg = valid_resume_session()
    assert MessageValidator.validate_resume_session(msg) is None


def test_resume_session_invalid_seq():
    msg = ResumeSession(
        session_id="sess-001",
        timestamp_ms=2500.0,
        last_seq_a2b=-2,
        last_seq_b2a=38,
    )
    error = MessageValidator.validate_resume_session(msg)
    assert error is not None and "last_seq" in error
