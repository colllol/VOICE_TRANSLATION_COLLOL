"""Tests for session state and queue management."""
import pytest
from protocol.session_manager import (
    BackpressureError,
    SessionManager,
    SessionQueue,
)
from protocol.messages import (
    AudioChunk,
    Direction,
    ErrorCode,
    SessionState,
    ResumeSession,
)
from protocol.fixtures import valid_audio_chunk, valid_resume_session


def test_session_start():
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    assert mgr.state == SessionState.IDLE
    mgr.start()
    assert mgr.state == SessionState.ACTIVE
    assert mgr.get_queue_depth(Direction.A_TO_B) == 0
    assert mgr.get_queue_depth(Direction.B_TO_A) == 0


def test_process_chunk_monotonic_sequence():
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    chunk0 = valid_audio_chunk(seq=0, direction=Direction.A_TO_B)
    chunk1 = valid_audio_chunk(seq=1, direction=Direction.A_TO_B)

    mgr.process_chunk(chunk0)
    mgr.process_chunk(chunk1)

    assert mgr.chunks_processed == 2
    assert mgr.get_queue_depth(Direction.A_TO_B) == 2


def test_process_chunk_stale_sequence_rejected():
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    chunk1 = valid_audio_chunk(seq=1, direction=Direction.A_TO_B)
    chunk0 = valid_audio_chunk(seq=0, direction=Direction.A_TO_B)

    mgr.process_chunk(chunk1)

    with pytest.raises(ValueError, match=ErrorCode.STALE_SEQUENCE.value):
        mgr.process_chunk(chunk0)

    counters = mgr.get_counters()
    assert counters["dropped_a2b"] == 2  # gap 0 + explicit drop


def test_process_chunk_duplicate_rejected():
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    chunk = valid_audio_chunk(seq=0, direction=Direction.A_TO_B)

    mgr.process_chunk(chunk)

    with pytest.raises(ValueError, match=ErrorCode.DUPLICATE_SEQUENCE.value):
        mgr.process_chunk(chunk)

    counters = mgr.get_counters()
    assert counters["dropped_a2b"] == 1


def test_process_chunk_with_gap():
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    chunk0 = valid_audio_chunk(seq=0, direction=Direction.A_TO_B)
    chunk5 = valid_audio_chunk(seq=5, direction=Direction.A_TO_B)

    mgr.process_chunk(chunk0)
    mgr.process_chunk(chunk5)

    counters = mgr.get_counters()
    assert counters["dropped_a2b"] == 4  # sequences 1-4 missing


def test_backpressure_exceeds_max_queue():
    mgr = SessionManager(session_id="sess-001", max_queue_size=2)
    mgr.start()

    chunk0 = valid_audio_chunk(seq=0, direction=Direction.A_TO_B)
    chunk1 = valid_audio_chunk(seq=1, direction=Direction.A_TO_B)
    chunk2 = valid_audio_chunk(seq=2, direction=Direction.A_TO_B)

    mgr.process_chunk(chunk0)
    mgr.process_chunk(chunk1)

    with pytest.raises(BackpressureError, match="queue at 2"):
        mgr.process_chunk(chunk2)


def test_cancel_clears_state():
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    chunk0 = valid_audio_chunk(seq=0, direction=Direction.A_TO_B)
    mgr.process_chunk(chunk0)

    assert mgr.get_queue_depth(Direction.A_TO_B) == 1

    mgr.cancel()

    assert mgr.state == SessionState.CANCELLED
    assert mgr.get_queue_depth(Direction.A_TO_B) == 0
    assert mgr.seq_state[Direction.A_TO_B.value].expected_seq == 0


def test_resume_advances_sequence():
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    resume_msg = ResumeSession(
        session_id="sess-001",
        timestamp_ms=3000.0,
        last_seq_a2b=42,
        last_seq_b2a=38,
    )

    mgr.resume(resume_msg)

    assert mgr.seq_state[Direction.A_TO_B.value].expected_seq == 43
    assert mgr.seq_state[Direction.B_TO_A.value].expected_seq == 39


def test_bidirectional_independence():
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    chunk_a2b = valid_audio_chunk(seq=0, direction=Direction.A_TO_B)
    chunk_b2a = valid_audio_chunk(seq=0, direction=Direction.B_TO_A)

    mgr.process_chunk(chunk_a2b)
    mgr.process_chunk(chunk_b2a)

    assert mgr.get_queue_depth(Direction.A_TO_B) == 1
    assert mgr.get_queue_depth(Direction.B_TO_A) == 1

    counters = mgr.get_counters()
    assert counters["chunks_processed"] == 2
