"""Session state and queue management for transport."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Deque
from collections import deque

from protocol.messages import (
    AudioChunk,
    CancelSession,
    Direction,
    ErrorCode,
    ResumeSession,
    SessionStart,
    SessionState,
)


class BackpressureError(RuntimeError):
    """Queue exceeded max_queue_size."""


@dataclass
class SequenceState:
    """Per-direction sequence tracking."""
    expected_seq: int = 0
    received_seq: int = -1
    dropped_count: int = 0


@dataclass
class SessionQueue:
    """Single direction queue with backpressure."""
    direction: Direction
    max_size: int
    items: Deque[AudioChunk] = field(default_factory=deque)

    def put(self, chunk: AudioChunk) -> None:
        if len(self.items) >= self.max_size:
            raise BackpressureError(
                f"{self.direction}: queue at {self.max_size}, dropping chunk"
            )
        self.items.append(chunk)

    def get(self) -> AudioChunk | None:
        return self.items.popleft() if self.items else None

    def clear(self) -> None:
        self.items.clear()

    def size(self) -> int:
        return len(self.items)


@dataclass
class SessionManager:
    """Tracks session lifecycle, sequence ordering, and backpressure per direction."""
    session_id: str
    state: SessionState = SessionState.IDLE
    seq_state: dict[str, SequenceState] = field(default_factory=lambda: {
        Direction.A_TO_B.value: SequenceState(),
        Direction.B_TO_A.value: SequenceState(),
    })
    queues: dict[str, SessionQueue] = field(default_factory=dict)
    max_queue_size: int = 100
    chunks_processed: int = 0

    def start(self) -> None:
        if self.state != SessionState.IDLE:
            raise RuntimeError(f"cannot start session in {self.state} state")
        self.state = SessionState.ACTIVE
        # Initialize queues
        for direction in (Direction.A_TO_B.value, Direction.B_TO_A.value):
            self.queues[direction] = SessionQueue(
                direction=Direction(direction),
                max_size=self.max_queue_size,
            )

    def process_chunk(self, chunk: AudioChunk) -> None:
        """Validate sequence order and enqueue. Raises BackpressureError or ValueError."""
        if self.state != SessionState.ACTIVE:
            raise RuntimeError(f"session in {self.state} state, cannot accept chunks")

        direction_str = chunk.direction.value
        seq_st = self.seq_state[direction_str]

        # Detect duplicate (exact match) or stale (older than last received)
        if chunk.seq == seq_st.received_seq:
            seq_st.dropped_count += 1
            raise ValueError(ErrorCode.DUPLICATE_SEQUENCE.value)
        if chunk.seq < seq_st.expected_seq:
            seq_st.dropped_count += 1
            raise ValueError(ErrorCode.STALE_SEQUENCE.value)

        # Gap is allowed (network loss), but track it
        if chunk.seq > seq_st.expected_seq:
            gap = chunk.seq - seq_st.expected_seq
            seq_st.dropped_count += gap

        seq_st.expected_seq = chunk.seq + 1
        seq_st.received_seq = chunk.seq
        self.chunks_processed += 1

        # Enqueue with backpressure
        self.queues[direction_str].put(chunk)

    def cancel(self) -> None:
        """Clear queues and reset sequence state."""
        for direction in (Direction.A_TO_B.value, Direction.B_TO_A.value):
            self.queues[direction].clear()
            self.seq_state[direction] = SequenceState()
        self.state = SessionState.CANCELLED

    def resume(self, msg: ResumeSession) -> None:
        """Reconnect and skip stale chunks up to acknowledged sequence."""
        if self.state not in (SessionState.ACTIVE, SessionState.IDLE):
            raise RuntimeError(f"cannot resume from {self.state} state")

        self.state = SessionState.ACTIVE

        # Client acked up to these sequences; advance our expected pointers
        self.seq_state[Direction.A_TO_B.value].expected_seq = msg.last_seq_a2b + 1
        self.seq_state[Direction.B_TO_A.value].expected_seq = msg.last_seq_b2a + 1

    def get_queue_depth(self, direction: Direction) -> int:
        return self.queues[direction.value].size()

    def get_counters(self) -> dict[str, int]:
        return {
            "chunks_processed": self.chunks_processed,
            "queue_a2b_size": self.get_queue_depth(Direction.A_TO_B),
            "queue_b2a_size": self.get_queue_depth(Direction.B_TO_A),
            "dropped_a2b": self.seq_state[Direction.A_TO_B.value].dropped_count,
            "dropped_b2a": self.seq_state[Direction.B_TO_A.value].dropped_count,
        }
