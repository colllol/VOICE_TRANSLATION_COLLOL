"""Tests for session service boundary."""
import pytest

from backend.session import SessionService, SessionNotFoundError
from protocol.fixtures import (
    valid_audio_chunk,
    valid_cancel_session,
    valid_resume_session,
    valid_session_end,
    valid_session_start,
)
from protocol.messages import (
    AudioChunk,
    CancelSession,
    Direction,
    ErrorCode,
    ResumeSession,
    SessionEnd,
    SessionStart,
)


def test_start_session_success():
    svc = SessionService()
    msg = valid_session_start()

    err = svc.start_session(msg)

    assert err is None
    assert svc.session_count() == 1
    assert msg.session_id in svc.list_sessions()


def test_start_session_duplicate():
    svc = SessionService()
    msg = valid_session_start()

    svc.start_session(msg)
    err = svc.start_session(msg)

    assert err is not None
    assert err.code == ErrorCode.INTERNAL_ERROR
    assert "already active" in err.detail


def test_start_session_invalid_message():
    svc = SessionService()
    msg = SessionStart(
        session_id="",  # invalid
        timestamp_ms=1000.0,
        source_lang="vi",
        target_lang="en",
    )

    err = svc.start_session(msg)

    assert err is not None
    assert err.code == ErrorCode.INVALID_MESSAGE
    assert "session_id" in err.detail


def test_process_audio_chunk_success():
    svc = SessionService()
    start_msg = valid_session_start()
    svc.start_session(start_msg)

    chunk = valid_audio_chunk(session_id=start_msg.session_id, seq=0)
    err = svc.process_audio_chunk(chunk)

    assert err is None
    mgr = svc.get_session(start_msg.session_id)
    assert mgr.chunks_processed == 1


def test_process_audio_chunk_session_not_found():
    svc = SessionService()
    chunk = valid_audio_chunk(session_id="unknown", seq=0)

    err = svc.process_audio_chunk(chunk)

    assert err is not None
    assert err.code == ErrorCode.SESSION_NOT_ACTIVE
    assert "not found" in err.detail


def test_process_audio_chunk_invalid_message():
    svc = SessionService()
    msg = AudioChunk(
        session_id="sess-001",
        direction=Direction.A_TO_B,
        seq=-1,  # invalid
        timestamp_ms=1000.0,
        payload=b"audio",
    )

    err = svc.process_audio_chunk(msg)

    assert err is not None
    assert err.code == ErrorCode.INVALID_MESSAGE
    assert "seq" in err.detail


def test_process_audio_chunk_stale_sequence():
    svc = SessionService()
    start_msg = valid_session_start()
    svc.start_session(start_msg)

    chunk1 = valid_audio_chunk(session_id=start_msg.session_id, seq=1)
    chunk0 = valid_audio_chunk(session_id=start_msg.session_id, seq=0)

    svc.process_audio_chunk(chunk1)
    err = svc.process_audio_chunk(chunk0)

    assert err is not None
    assert err.code == ErrorCode.STALE_SEQUENCE


def test_process_audio_chunk_duplicate_sequence():
    svc = SessionService()
    start_msg = valid_session_start()
    svc.start_session(start_msg)

    chunk = valid_audio_chunk(session_id=start_msg.session_id, seq=0)

    svc.process_audio_chunk(chunk)
    err = svc.process_audio_chunk(chunk)

    assert err is not None
    assert err.code == ErrorCode.DUPLICATE_SEQUENCE


def test_process_audio_chunk_backpressure():
    svc = SessionService()
    start_msg = SessionStart(
        session_id="sess-001",
        timestamp_ms=1000.0,
        source_lang="vi",
        target_lang="en",
        max_queue_size=2,
    )
    svc.start_session(start_msg)

    for i in range(2):
        chunk = valid_audio_chunk(session_id=start_msg.session_id, seq=i)
        svc.process_audio_chunk(chunk)

    chunk2 = valid_audio_chunk(session_id=start_msg.session_id, seq=2)
    err = svc.process_audio_chunk(chunk2)

    assert err is not None
    assert err.code == ErrorCode.BACKPRESSURE_EXCEEDED
    assert "queue full" in err.detail


def test_end_session_success():
    svc = SessionService()
    start_msg = valid_session_start()
    svc.start_session(start_msg)

    end_msg = valid_session_end(session_id=start_msg.session_id)
    err = svc.end_session(end_msg)

    assert err is None
    assert svc.session_count() == 0


def test_end_session_not_found():
    svc = SessionService()
    end_msg = valid_session_end(session_id="unknown")

    err = svc.end_session(end_msg)

    assert err is not None
    assert err.code == ErrorCode.SESSION_NOT_ACTIVE


def test_end_session_invalid_message():
    svc = SessionService()
    msg = SessionEnd(
        session_id="sess-001",
        timestamp_ms=1000.0,
        reason="invalid",  # type: ignore
    )

    err = svc.end_session(msg)

    assert err is not None
    assert err.code == ErrorCode.INVALID_MESSAGE
    assert "reason" in err.detail


def test_cancel_session_success():
    svc = SessionService()
    start_msg = valid_session_start()
    svc.start_session(start_msg)

    chunk = valid_audio_chunk(session_id=start_msg.session_id, seq=0)
    svc.process_audio_chunk(chunk)

    cancel_msg = valid_cancel_session(session_id=start_msg.session_id)
    err = svc.cancel_session(cancel_msg)

    assert err is None
    assert svc.session_count() == 0


def test_cancel_session_not_found():
    svc = SessionService()
    cancel_msg = valid_cancel_session(session_id="unknown")

    err = svc.cancel_session(cancel_msg)

    assert err is not None
    assert err.code == ErrorCode.SESSION_NOT_ACTIVE


def test_resume_session_success():
    svc = SessionService()
    start_msg = valid_session_start()
    svc.start_session(start_msg)

    resume_msg = valid_resume_session(
        session_id=start_msg.session_id,
        last_seq_a2b=10,
        last_seq_b2a=5,
    )
    err = svc.resume_session(resume_msg)

    assert err is None
    mgr = svc.get_session(start_msg.session_id)
    assert mgr.seq_state[Direction.A_TO_B.value].expected_seq == 11
    assert mgr.seq_state[Direction.B_TO_A.value].expected_seq == 6


def test_resume_session_not_found():
    svc = SessionService()
    resume_msg = valid_resume_session(session_id="unknown")

    err = svc.resume_session(resume_msg)

    assert err is not None
    assert err.code == ErrorCode.SESSION_NOT_ACTIVE


def test_get_session_not_found():
    svc = SessionService()

    with pytest.raises(SessionNotFoundError, match="sess-001 not found"):
        svc.get_session("sess-001")


def test_bidirectional_independence():
    svc = SessionService()
    start_msg = valid_session_start()
    svc.start_session(start_msg)

    chunk_a2b = valid_audio_chunk(
        session_id=start_msg.session_id,
        seq=0,
        direction=Direction.A_TO_B,
    )
    chunk_b2a = valid_audio_chunk(
        session_id=start_msg.session_id,
        seq=0,
        direction=Direction.B_TO_A,
    )

    err1 = svc.process_audio_chunk(chunk_a2b)
    err2 = svc.process_audio_chunk(chunk_b2a)

    assert err1 is None
    assert err2 is None

    mgr = svc.get_session(start_msg.session_id)
    assert mgr.get_queue_depth(Direction.A_TO_B) == 1
    assert mgr.get_queue_depth(Direction.B_TO_A) == 1


def test_multiple_sessions_isolated():
    svc = SessionService()

    start1 = SessionStart(
        session_id="sess-001",
        timestamp_ms=1000.0,
        source_lang="vi",
        target_lang="en",
    )
    start2 = SessionStart(
        session_id="sess-002",
        timestamp_ms=2000.0,
        source_lang="en",
        target_lang="vi",
    )

    svc.start_session(start1)
    svc.start_session(start2)

    chunk1 = valid_audio_chunk(session_id="sess-001", seq=0)
    chunk2 = valid_audio_chunk(session_id="sess-002", seq=0)

    svc.process_audio_chunk(chunk1)
    svc.process_audio_chunk(chunk2)

    assert svc.session_count() == 2
    mgr1 = svc.get_session("sess-001")
    mgr2 = svc.get_session("sess-002")
    assert mgr1.chunks_processed == 1
    assert mgr2.chunks_processed == 1


def test_terminal_session_retention():
    svc = SessionService()
    start_msg = valid_session_start()
    svc.start_session(start_msg)

    end_msg = valid_session_end(session_id=start_msg.session_id)
    svc.end_session(end_msg)

    assert svc.session_count() == 0
    assert start_msg.session_id in svc.list_retained()
    retained = svc.get_retained_session(start_msg.session_id)
    assert retained is not None
    assert retained.reason == "completed"
    assert retained.manager.session_id == start_msg.session_id


def test_cancelled_session_retention():
    svc = SessionService()
    start_msg = valid_session_start()
    svc.start_session(start_msg)

    cancel_msg = valid_cancel_session(session_id=start_msg.session_id)
    svc.cancel_session(cancel_msg)

    assert svc.session_count() == 0
    assert start_msg.session_id in svc.list_retained()
    retained = svc.get_retained_session(start_msg.session_id)
    assert retained is not None
    assert retained.reason == "cancelled"


def test_retention_bounded_by_max():
    svc = SessionService(max_retained=2)

    for i in range(3):
        start_msg = SessionStart(
            session_id=f"sess-{i:03d}",
            timestamp_ms=1000.0 + i,
            source_lang="vi",
            target_lang="en",
        )
        svc.start_session(start_msg)
        end_msg = valid_session_end(session_id=start_msg.session_id)
        svc.end_session(end_msg)

    assert len(svc.list_retained()) == 2
    assert "sess-000" not in svc.list_retained()
    assert "sess-001" in svc.list_retained()
    assert "sess-002" in svc.list_retained()


def test_expire_inactive_removes_old_sessions():
    svc = SessionService()
    start_msg = valid_session_start()
    svc.start_session(start_msg)

    end_msg = valid_session_end(session_id=start_msg.session_id)
    svc.end_session(end_msg)

    retained = svc.get_retained_session(start_msg.session_id)
    assert retained is not None
    ended_at = retained.ended_at_ms

    expired = svc.expire_inactive(ended_at + 5000, 3000)

    assert start_msg.session_id in expired
    assert len(svc.list_retained()) == 0
    assert svc.get_retained_session(start_msg.session_id) is None


def test_expire_inactive_keeps_recent_sessions():
    svc = SessionService()
    start_msg = valid_session_start()
    svc.start_session(start_msg)

    end_msg = valid_session_end(session_id=start_msg.session_id)
    svc.end_session(end_msg)

    retained = svc.get_retained_session(start_msg.session_id)
    assert retained is not None
    ended_at = retained.ended_at_ms

    expired = svc.expire_inactive(ended_at + 1000, 3000)

    assert len(expired) == 0
    assert len(svc.list_retained()) == 1
    assert svc.get_retained_session(start_msg.session_id) is not None
