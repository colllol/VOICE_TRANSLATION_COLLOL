"""Synchronous fake for the two VoIP media hooks on device A.

Only a controlled VoIP implementation can call these hooks. Passing these unit tests
is not evidence that Android exposes third-party call audio or that B hears it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


class RouteError(RuntimeError):
    """An invalid or stale audio frame reached the routing boundary."""


@dataclass
class DirectionState:
    last_seq: int = -1
    raw_frames: int = 0
    translated_frames: int = 0
    dropped_frames: int = 0


class TranslationRoute:
    """Model one call on A; B has no translation tool or controls.

    The injected `translate(payload, direction)` callback is a deterministic fake.
    Real ASR/NMT/TTS is asynchronous and must obey the same fail-closed output rule.
    """

    def __init__(self, translate: Callable[[bytes, str], bytes]) -> None:
        self._translate = translate
        self._active = False
        self._state = {direction: DirectionState() for direction in ("a2b", "b2a")}

    def start(self) -> None:
        """A alone activates translation; both directions are enabled together."""
        self._active = True

    def stop(self) -> None:
        """Cancel this session, clearing ordering state before the next call."""
        self._active = False
        self._state = {direction: DirectionState() for direction in ("a2b", "b2a")}

    def outbound_from_mic_a(self, payload: bytes, seq: int) -> bytes | None:
        """Return frame for outbound VoIP encoder, not Android's local speaker."""
        return self._process("a2b", payload, seq)

    def inbound_from_peer_b(self, payload: bytes, seq: int) -> bytes | None:
        """Return frame for A's render path, not for the VoIP outbound encoder."""
        return self._process("b2a", payload, seq)

    def _process(self, direction: str, payload: bytes, seq: int) -> bytes | None:
        state = self._state[direction]
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
            raise RouteError(f"{direction}: invalid sequence")
        if seq <= state.last_seq:
            raise RouteError(f"{direction}: stale or duplicate sequence {seq}")
        state.last_seq = seq
        if not isinstance(payload, bytes):
            raise RouteError(f"{direction}: expected PCM bytes")
        if not payload:
            state.dropped_frames += 1
            return None
        if not self._active:
            state.raw_frames += 1
            return payload
        try:
            translated = self._translate(payload, direction)
        except Exception:
            state.dropped_frames += 1
            return None
        if not isinstance(translated, bytes) or not translated:
            state.dropped_frames += 1
            return None
        state.translated_frames += 1
        return translated

    def counters(self, direction: str) -> DirectionState:
        if direction not in self._state:
            raise RouteError(f"unknown direction {direction}")
        s = self._state[direction]
        return DirectionState(s.last_seq, s.raw_frames, s.translated_frames, s.dropped_frames)