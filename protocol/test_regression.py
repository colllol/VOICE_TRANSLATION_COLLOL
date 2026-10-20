"""Regression tests for VT-002 contract defects."""
import pytest
from protocol.session_manager import SessionManager
from protocol.messages import Direction, SessionState, CancelSession, ResumeSession
from protocol.validation import ValidationError
from protocol.fixtures import (
    valid_audio_chunk,
    valid_cancel_session,
    valid_resume_session,
)


def test_process_chunk_rejects_wrong_session_id():
    """Defect 2: session_id validation on process_chunk."""
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    wrong_chunk = valid_audio_chunk(session_id="sess-999", seq=0)

    with pytest.raises(ValueError, match="session_id mismatch"):
        mgr.process_chunk(wrong_chunk)


def test_cancel_rejects_wrong_session_id():
    """Defect 2: session_id validation on cancel."""
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    wrong_cancel = valid_cancel_session(session_id="sess-999")

    with pytest.raises(ValueError, match="session_id mismatch"):
        mgr.cancel(wrong_cancel)


def test_resume_rejects_wrong_session_id():
    """Defect 2: session_id validation on resume."""
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    wrong_resume = valid_resume_session(session_id="sess-999")

    with pytest.raises(ValueError, match="session_id mismatch"):
        mgr.resume(wrong_resume)


def test_resume_clears_stale_queued_chunks():
    """Defect 1: resume must clear queues to prevent stale delivery."""
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    chunk0 = valid_audio_chunk(seq=0, direction=Direction.A_TO_B)
    chunk1 = valid_audio_chunk(seq=1, direction=Direction.A_TO_B)
    mgr.process_chunk(chunk0)
    mgr.process_chunk(chunk1)

    assert mgr.get_queue_depth(Direction.A_TO_B) == 2

    # Simulate reconnect: client acked seq=5, so 0,1 are stale
    resume_msg = valid_resume_session(session_id="sess-001")
    resume_msg = resume_msg.__class__(
        session_id="sess-001",
        timestamp_ms=3000.0,
        last_seq_a2b=5,
        last_seq_b2a=-1,
    )
    mgr.resume(resume_msg)

    # Queues must be empty after resume
    assert mgr.get_queue_depth(Direction.A_TO_B) == 0
    assert mgr.get_queue_depth(Direction.B_TO_A) == 0
    assert mgr.seq_state[Direction.A_TO_B.value].expected_seq == 6


def test_cancel_validates_message_fields():
    """Defect 3: cancel must validate CancelSession message fields."""
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    from protocol.validation import MessageValidator
    cancel_msg = valid_cancel_session(session_id="sess-001")

    # Validate message structure
    error = MessageValidator.validate_cancel_session(cancel_msg)
    assert error is None

    mgr.cancel(cancel_msg)
    assert mgr.state == SessionState.CANCELLED


def test_resume_validates_message_fields():
    """Defect 3: resume must validate ResumeSession message fields."""
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    from protocol.validation import MessageValidator
    resume_msg = valid_resume_session(session_id="sess-001")

    # Validate message structure
    error = MessageValidator.validate_resume_session(resume_msg)
    assert error is None

    mgr.resume(resume_msg)
    assert mgr.state == SessionState.ACTIVE


def test_process_chunk_atomic_under_backpressure():
    """Defect 4: process_chunk must be atomic - no state changes if queue.put fails."""
    from protocol.session_manager import BackpressureError

    mgr = SessionManager(session_id="sess-001", max_queue_size=2)
    mgr.start()

    chunk0 = valid_audio_chunk(seq=0, direction=Direction.A_TO_B)
    chunk1 = valid_audio_chunk(seq=1, direction=Direction.A_TO_B)
    chunk2 = valid_audio_chunk(seq=2, direction=Direction.A_TO_B)

    mgr.process_chunk(chunk0)
    mgr.process_chunk(chunk1)

    # Capture state before rejected chunk
    expected_seq_before = mgr.seq_state[Direction.A_TO_B.value].expected_seq
    received_seq_before = mgr.seq_state[Direction.A_TO_B.value].received_seq
    dropped_count_before = mgr.seq_state[Direction.A_TO_B.value].dropped_count
    chunks_processed_before = mgr.chunks_processed

    # Queue is full, should reject without mutating state
    with pytest.raises(BackpressureError, match="queue at 2"):
        mgr.process_chunk(chunk2)

    # Verify state unchanged
    assert mgr.seq_state[Direction.A_TO_B.value].expected_seq == expected_seq_before
    assert mgr.seq_state[Direction.A_TO_B.value].received_seq == received_seq_before
    assert mgr.seq_state[Direction.A_TO_B.value].dropped_count == dropped_count_before
    assert mgr.chunks_processed == chunks_processed_before

    # After draining queue, same chunk should succeed
    mgr.queues[Direction.A_TO_B.value].get()
    mgr.process_chunk(chunk2)
    assert mgr.chunks_processed == chunks_processed_before + 1
    assert mgr.seq_state[Direction.A_TO_B.value].expected_seq == 3


def test_cancel_rejects_invalid_timestamp():
    """cancel() must validate message fields including timestamp."""
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    invalid_cancel = CancelSession(session_id="sess-001", timestamp_ms=-1.0)

    with pytest.raises(ValidationError, match="timestamp_ms must be finite and non-negative"):
        mgr.cancel(invalid_cancel)


def test_resume_rejects_invalid_sequence():
    """resume() must validate message fields including sequence numbers."""
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()

    invalid_resume = ResumeSession(
        session_id="sess-001",
        timestamp_ms=1000.0,
        last_seq_a2b=-2,
        last_seq_b2a=0,
    )

    with pytest.raises(ValidationError, match="last_seq_a2b must be >= -1"):
        mgr.resume(invalid_resume)
