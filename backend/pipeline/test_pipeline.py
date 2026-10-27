"""Focused contract tests for the VT-013 translation pipeline boundary."""

import pytest

from backend.pipeline import (
    DuplicateSequenceError,
    PipelineCancelledError,
    PipelineInputError,
    QueueFullError,
    StaleSequenceError,
    TranslationPipeline,
)
from backend.providers.fake import create_fake_providers
from protocol.messages import AudioChunk, Direction


SESSION_ID = "pipeline-test"


def chunk(direction: Direction, seq: int, payload: bytes = b"audio") -> AudioChunk:
    return AudioChunk(
        session_id=SESSION_ID,
        direction=direction,
        seq=seq,
        timestamp_ms=1000.0 + seq,
        payload=payload,
    )


def pipeline(max_queue_size: int = 4) -> TranslationPipeline:
    return TranslationPipeline(
        session_id=SESSION_ID,
        source_lang="en",
        target_lang="vi",
        providers=create_fake_providers(),
        max_queue_size=max_queue_size,
    )


def test_a2b_and_b2a_are_independent_provider_paths():
    pipe = pipeline()
    pipe.submit(chunk(Direction.A_TO_B, 0, b"from-a"))
    pipe.submit(chunk(Direction.B_TO_A, 0, b"from-b"))

    a2b_output = pipe.process_next(Direction.A_TO_B)
    assert a2b_output is not None
    assert a2b_output.direction is Direction.B_TO_A
    assert a2b_output.seq == 0
    assert a2b_output.payload.startswith(b"FAKE_AUDIO_TEST")
    assert pipe.queue_depth(Direction.B_TO_A) == 1

    b2a_output = pipe.process_next(Direction.B_TO_A)
    assert b2a_output is not None
    assert b2a_output.direction is Direction.A_TO_B
    assert b2a_output.seq == 0
    assert b2a_output.payload.startswith(b"FAKE_AUDIO_TEST")


def test_ordering_accepts_gaps_but_rejects_duplicate_and_stale_sequences():
    pipe = pipeline()
    pipe.submit(chunk(Direction.A_TO_B, 0))
    pipe.submit(chunk(Direction.A_TO_B, 2))

    with pytest.raises(DuplicateSequenceError):
        pipe.submit(chunk(Direction.A_TO_B, 2))
    with pytest.raises(StaleSequenceError):
        pipe.submit(chunk(Direction.A_TO_B, 1))

    outputs = [
        pipe.process_next(Direction.A_TO_B),
        pipe.process_next(Direction.A_TO_B),
    ]
    assert [output.timestamp_ms for output in outputs] == [1000.0, 1002.0]
    assert [output.seq for output in outputs] == [0, 1]


def test_backpressure_is_bounded_and_does_not_advance_sequence():
    pipe = pipeline(max_queue_size=1)
    pipe.submit(chunk(Direction.A_TO_B, 0))

    with pytest.raises(QueueFullError):
        pipe.submit(chunk(Direction.A_TO_B, 1))

    assert pipe.queue_depth(Direction.A_TO_B) == 1
    assert pipe.process_next(Direction.A_TO_B).seq == 0
    pipe.submit(chunk(Direction.A_TO_B, 1))
    assert pipe.process_next(Direction.A_TO_B).seq == 1


def test_cancellation_clears_both_queues_and_blocks_new_work():
    pipe = pipeline()
    pipe.submit(chunk(Direction.A_TO_B, 0))
    pipe.submit(chunk(Direction.B_TO_A, 0))

    pipe.cancel()

    assert pipe.cancelled is True
    assert pipe.queue_depth(Direction.A_TO_B) == 0
    assert pipe.queue_depth(Direction.B_TO_A) == 0
    with pytest.raises(PipelineCancelledError):
        pipe.submit(chunk(Direction.A_TO_B, 1))
    with pytest.raises(PipelineCancelledError):
        pipe.process_next(Direction.B_TO_A)


def test_output_is_opaque_audio_and_never_contains_internal_transcript():
    pipe = pipeline()
    pipe.submit(chunk(Direction.A_TO_B, 0, b"source-audio"))

    output = pipe.process_next(Direction.A_TO_B)

    assert output is not None
    assert isinstance(output.payload, bytes)
    assert b"test utterance" not in output.payload
    assert b"[en->vi]" not in output.payload
    assert output.payload.startswith(b"FAKE_AUDIO_TEST")


def test_input_session_and_payload_are_checked_at_pipeline_boundary():
    pipe = pipeline()
    wrong_session = AudioChunk(
        session_id="other",
        direction=Direction.A_TO_B,
        seq=0,
        timestamp_ms=1000.0,
        payload=b"audio",
    )
    with pytest.raises(PipelineInputError, match="session_id"):
        pipe.submit(wrong_session)

    with pytest.raises(PipelineInputError, match="payload"):
        pipe.submit(chunk(Direction.A_TO_B, 0, b""))
