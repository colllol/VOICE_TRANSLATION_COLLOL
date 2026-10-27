"""Synchronous VT-013 boundary from audio chunks to audio chunks.

The provider transcript and translated text are implementation details. The
public pipeline surface accepts and returns protocol ``AudioChunk`` objects,
so text never crosses the transport boundary.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock, RLock
from typing import Deque, Final

from backend.providers.base import ASRProvider, NMTProvider, TTSProvider
from protocol.messages import AudioChunk, Direction


class PipelineError(RuntimeError):
    """Base class for pipeline lifecycle and capacity errors."""


class PipelineInputError(ValueError):
    """An input chunk does not belong to this pipeline or is invalid."""


class DuplicateSequenceError(PipelineInputError):
    """An input sequence was already accepted for its direction."""


class StaleSequenceError(PipelineInputError):
    """An input sequence is older than the next accepted sequence."""


class QueueFullError(PipelineError):
    """The bounded input queue for a direction is full."""


class PipelineCancelledError(PipelineError):
    """The pipeline was cancelled and cannot accept or process more work."""


@dataclass(frozen=True)
class _ProviderSet:
    asr: ASRProvider
    nmt: NMTProvider
    tts: TTSProvider


@dataclass
class _SequenceState:
    next_input_seq: int = 0
    next_output_seq: int = 0


class TranslationPipeline:
    """Translate each direction through an isolated, bounded FIFO queue.

    ``submit`` is the transport-facing operation. ``process_next`` performs
    one complete ASR -> NMT -> TTS operation synchronously and returns the
    translated audio for the same media path: ``A_TO_B`` remains outbound to
    B, while ``B_TO_A`` remains inbound for A's render path. A gap in input
    sequence numbers is allowed by the existing protocol; duplicates and older
    values are rejected. Cancellation clears pending input and prevents new
    work.
    """

    _DIRECTIONS: Final[tuple[Direction, Direction]] = (
        Direction.A_TO_B,
        Direction.B_TO_A,
    )

    def __init__(
        self,
        session_id: str,
        source_lang: str,
        target_lang: str,
        providers: tuple[ASRProvider, NMTProvider, TTSProvider],
        max_queue_size: int = 100,
    ) -> None:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        if not isinstance(source_lang, str) or not source_lang.strip():
            raise ValueError("source_lang must be a non-empty string")
        if not isinstance(target_lang, str) or not target_lang.strip():
            raise ValueError("target_lang must be a non-empty string")
        if isinstance(max_queue_size, bool) or not isinstance(max_queue_size, int) or max_queue_size <= 0:
            raise ValueError("max_queue_size must be a positive integer")
        if not isinstance(providers, tuple) or len(providers) != 3:
            raise ValueError("providers must be an (ASR, NMT, TTS) tuple")

        self.session_id = session_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._providers = _ProviderSet(*providers)
        self._queues: dict[Direction, Deque[AudioChunk]] = {
            direction: deque() for direction in self._DIRECTIONS
        }
        self._sequences: dict[Direction, _SequenceState] = {
            direction: _SequenceState() for direction in self._DIRECTIONS
        }
        self.max_queue_size = max_queue_size
        self.cancelled = False
        self._state_lock = RLock()
        self._processing_locks = {direction: Lock() for direction in self._DIRECTIONS}

    def submit(self, chunk: AudioChunk) -> None:
        """Validate and enqueue one inbound audio chunk."""
        if not isinstance(chunk, AudioChunk):
            raise PipelineInputError("chunk must be an AudioChunk")
        if chunk.session_id != self.session_id:
            raise PipelineInputError(
                f"session_id mismatch: expected {self.session_id}, got {chunk.session_id}"
            )
        if not isinstance(chunk.direction, Direction):
            raise PipelineInputError("direction must be a protocol Direction")
        if not isinstance(chunk.seq, int) or isinstance(chunk.seq, bool) or chunk.seq < 0:
            raise PipelineInputError("seq must be a non-negative integer")
        if not isinstance(chunk.payload, bytes) or not chunk.payload:
            raise PipelineInputError("payload must be non-empty bytes")

        with self._state_lock:
            if self.cancelled:
                raise PipelineCancelledError("pipeline is cancelled")
            state = self._sequences[chunk.direction]
            if chunk.seq < state.next_input_seq:
                if chunk.seq == state.next_input_seq - 1:
                    raise DuplicateSequenceError(
                        f"duplicate sequence {chunk.seq} for {chunk.direction.value}"
                    )
                raise StaleSequenceError(
                    f"stale sequence {chunk.seq} for {chunk.direction.value}; "
                    f"next is {state.next_input_seq}"
                )
            queue = self._queues[chunk.direction]
            if len(queue) >= self.max_queue_size:
                raise QueueFullError(
                    f"queue full for {chunk.direction.value} at {self.max_queue_size}"
                )

            queue.append(chunk)
            state.next_input_seq = chunk.seq + 1

    def process_next(self, direction: Direction) -> AudioChunk | None:
        """Translate the oldest queued chunk for ``direction`` if present."""
        if not isinstance(direction, Direction):
            raise PipelineInputError("direction must be a protocol Direction")
        with self._processing_locks[direction]:
            return self._process_next_locked(direction)

    def _process_next_locked(self, direction: Direction) -> AudioChunk | None:
        with self._state_lock:
            if self.cancelled:
                raise PipelineCancelledError("pipeline is cancelled")
            queue = self._queues[direction]
            if not queue:
                return None
            inbound = queue[0]
        source_lang, target_lang = self._languages(direction)
        try:
            transcript = self._providers.asr.transcribe(inbound.payload)
            translated_text = self._providers.nmt.translate(
                transcript,
                source_lang,
                target_lang,
            )
            output_audio = self._providers.tts.synthesize(translated_text, target_lang)
        except Exception as cause:
            with self._state_lock:
                if self.cancelled:
                    raise PipelineCancelledError(
                        "pipeline was cancelled during provider work"
                    ) from cause
            raise

        with self._state_lock:
            if self.cancelled:
                raise PipelineCancelledError("pipeline was cancelled during provider work")
            if not queue or queue[0] is not inbound:
                raise PipelineError("pipeline queue changed during provider work")
            output_state = self._sequences[direction]
            output = AudioChunk(
                session_id=self.session_id,
                direction=direction,
                seq=output_state.next_output_seq,
                timestamp_ms=inbound.timestamp_ms,
                payload=output_audio,
                is_final=inbound.is_final,
            )
            queue.popleft()
            output_state.next_output_seq += 1
            return output

    def cancel(self) -> None:
        """Drop queued work and permanently stop this pipeline."""
        with self._state_lock:
            self.cancelled = True
            for queue in self._queues.values():
                queue.clear()

    def queue_depth(self, direction: Direction) -> int:
        """Return pending inbound work for one direction."""
        if not isinstance(direction, Direction):
            raise PipelineInputError("direction must be a protocol Direction")
        with self._state_lock:
            return len(self._queues[direction])

    def _languages(self, direction: Direction) -> tuple[str, str]:
        if direction is Direction.A_TO_B:
            return self.source_lang, self.target_lang
        return self.target_lang, self.source_lang
