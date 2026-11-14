"""Deterministic duplex audio boundary for the computer vertical slice."""
from __future__ import annotations

import base64
from dataclasses import dataclass

from computer.server.contract import AudioFormat, AudioInput


class PipelineError(ValueError):
    """Input cannot be accepted by the duplex pipeline."""


@dataclass(frozen=True)
class AudioOutput:
    stream_id: str
    input_seq_start: int
    input_seq_end: int
    output_seq: int
    duration_ms: int
    data_b64: str


class DuplexPipeline:
    """Maintain independent sequence state and opaque audio output per direction."""

    def __init__(self, audio: AudioFormat) -> None:
        self.audio = audio
        self._next: dict[str, int] = {"a2b": 0, "b2a": 0}
        self._output: dict[str, int] = {"a2b": 0, "b2a": 0}
        self._cancelled = False

    def process(self, frame: AudioInput) -> AudioOutput:
        if self._cancelled:
            raise PipelineError("pipeline is cancelled")
        if frame.stream_id not in self._next:
            raise PipelineError("unknown stream")
        expected = self._next[frame.stream_id]
        if frame.seq < 0:
            raise PipelineError(f"stale sequence for {frame.stream_id}")
        if frame.seq < expected:
            kind = "duplicate" if frame.seq == expected - 1 else "stale"
            raise PipelineError(f"{kind} sequence for {frame.stream_id}")
        if frame.seq > expected:
            raise PipelineError(f"gap in sequence for {frame.stream_id}")
        output_seq = self._output[frame.stream_id]
        self._next[frame.stream_id] += 1
        self._output[frame.stream_id] += 1
        # Placeholder transform: preserves frame size and direction while the
        # provider ports are introduced. It is not a translation claim.
        transformed = bytes(value ^ 0xA5 for value in frame.data)
        return AudioOutput(
            stream_id=frame.stream_id,
            input_seq_start=frame.seq,
            input_seq_end=frame.seq,
            output_seq=output_seq,
            duration_ms=frame.duration_ms,
            data_b64=base64.b64encode(transformed).decode("ascii"),
        )

    def cancel(self) -> None:
        self._cancelled = True
