"""Duplex pipeline tests for the replacement computer server."""
import base64

import pytest

from computer.server.contract import AudioFormat, AudioInput
from computer.server.pipeline import DuplexPipeline, PipelineError


AUDIO = AudioFormat(16000, 1, "pcm_s16le", 20)


def frame(stream: str, seq: int = 0) -> AudioInput:
    return AudioInput(stream, seq, seq * 20, 20, bytes([seq & 0xFF]) * AUDIO.frame_bytes)


def test_each_direction_is_processed_independently():
    pipeline = DuplexPipeline(AUDIO)

    a2b = pipeline.process(frame("a2b"))
    b2a = pipeline.process(frame("b2a"))

    assert a2b.stream_id == "a2b"
    assert b2a.stream_id == "b2a"
    assert a2b.input_seq_start == 0
    assert b2a.input_seq_start == 0
    assert len(base64.b64decode(a2b.data_b64)) == AUDIO.frame_bytes


def test_duplicate_and_stale_sequences_are_rejected():
    pipeline = DuplexPipeline(AUDIO)
    pipeline.process(frame("a2b", 0))

    with pytest.raises(PipelineError, match="duplicate"):
        pipeline.process(frame("a2b", 0))
    pipeline.process(frame("a2b", 1))
    with pytest.raises(PipelineError, match="stale"):
        pipeline.process(frame("a2b", 0))


def test_gap_is_rejected_and_cancel_blocks_processing():
    pipeline = DuplexPipeline(AUDIO)
    pipeline.process(frame("a2b", 0))
    with pytest.raises(PipelineError, match="gap"):
        pipeline.process(frame("a2b", 2))

    pipeline.cancel()
    with pytest.raises(PipelineError, match="cancelled"):
        pipeline.process(frame("b2a", 0))
