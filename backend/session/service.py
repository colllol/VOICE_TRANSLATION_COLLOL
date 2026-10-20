"""Session service: lifecycle, validation, and isolation for transport."""
from __future__ import annotations

import time
from typing import Dict
from dataclasses import dataclass

from protocol.messages import (
    AudioChunk,
    CancelSession,
    Direction,
    ErrorCode,
    ErrorMessage,
    ResumeSession,
    SessionEnd,
    SessionStart,
)
from protocol.session_manager import BackpressureError, SessionManager, SessionState
from protocol.validation import MessageValidator, ValidationError


class SessionNotFoundError(ValueError):
    """Session ID not found in active sessions."""


class StaleSequenceError(ValueError):
    """Received chunk older than expected sequence."""


class DuplicateSequenceError(ValueError):
    """Received duplicate chunk sequence."""


@dataclass
class RetainedSession:
    """Terminal session kept for observability."""
    manager: SessionManager
    ended_at_ms: float
    reason: str


class SessionService:
    """Manages multiple isolated sessions with validation and error translation."""

    def __init__(self, max_retained: int = 100):
        self._sessions: Dict[str, SessionManager] = {}
        self._retained: Dict[str, RetainedSession] = {}
        self._max_retained = max_retained

    def start_session(self, msg: SessionStart) -> ErrorMessage | None:
        """Start new session; returns ErrorMessage on failure, None on success."""
        err = MessageValidator.validate_session_start(msg)
        if err:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.INVALID_MESSAGE,
                detail=f"SessionStart validation: {err}",
            )

        if msg.session_id in self._sessions:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.INTERNAL_ERROR,
                detail="session already active",
            )

        mgr = SessionManager(
            session_id=msg.session_id,
            max_queue_size=msg.max_queue_size,
        )
        mgr.start()
        self._sessions[msg.session_id] = mgr
        return None

    def process_audio_chunk(self, msg: AudioChunk) -> ErrorMessage | None:
        """Process audio chunk; returns ErrorMessage on failure, None on success."""
        err = MessageValidator.validate_audio_chunk(msg)
        if err:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.INVALID_MESSAGE,
                detail=f"AudioChunk validation: {err}",
            )

        mgr = self._sessions.get(msg.session_id)
        if not mgr:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.SESSION_NOT_ACTIVE,
                detail="session not found",
            )

        if mgr.state != SessionState.ACTIVE:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.SESSION_NOT_ACTIVE,
                detail=f"session in {mgr.state.value} state",
            )

        try:
            mgr.process_chunk(msg)
            return None
        except BackpressureError:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.BACKPRESSURE_EXCEEDED,
                detail=f"queue full for {msg.direction.value}",
            )
        except ValueError as e:
            # ponytail: stable error string mapping until SessionManager uses typed exceptions
            err_str = str(e)
            if ErrorCode.STALE_SEQUENCE.value in err_str:
                code = ErrorCode.STALE_SEQUENCE
            elif ErrorCode.DUPLICATE_SEQUENCE.value in err_str:
                code = ErrorCode.DUPLICATE_SEQUENCE
            else:
                code = ErrorCode.INTERNAL_ERROR
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=code,
                detail=err_str,
            )

    def end_session(self, msg: SessionEnd) -> ErrorMessage | None:
        """End session; returns ErrorMessage on failure, None on success."""
        err = MessageValidator.validate_session_end(msg)
        if err:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.INVALID_MESSAGE,
                detail=f"SessionEnd validation: {err}",
            )

        mgr = self._sessions.get(msg.session_id)
        if not mgr:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.SESSION_NOT_ACTIVE,
                detail="session not found",
            )

        if msg.reason == "cancelled":
            mgr.state = SessionState.CANCELLED
        else:
            mgr.state = SessionState.COMPLETED

        self._retain_session(mgr, msg.reason)
        del self._sessions[msg.session_id]
        return None

    def cancel_session(self, msg: CancelSession) -> ErrorMessage | None:
        """Cancel session; clears queues and removes session."""
        err = MessageValidator.validate_cancel_session(msg)
        if err:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.INVALID_MESSAGE,
                detail=f"CancelSession validation: {err}",
            )

        mgr = self._sessions.get(msg.session_id)
        if not mgr:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.SESSION_NOT_ACTIVE,
                detail="session not found",
            )

        mgr.cancel(msg)
        self._retain_session(mgr, "cancelled")
        del self._sessions[msg.session_id]
        return None

    def resume_session(self, msg: ResumeSession) -> ErrorMessage | None:
        """Resume session after reconnect."""
        err = MessageValidator.validate_resume_session(msg)
        if err:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.INVALID_MESSAGE,
                detail=f"ResumeSession validation: {err}",
            )

        mgr = self._sessions.get(msg.session_id)
        if not mgr:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.SESSION_NOT_ACTIVE,
                detail="session not found",
            )

        try:
            mgr.resume(msg)
            return None
        except RuntimeError as e:
            return ErrorMessage(
                session_id=msg.session_id,
                timestamp_ms=time.time() * 1000,
                code=ErrorCode.INTERNAL_ERROR,
                detail=str(e),
            )

    def _retain_session(self, mgr: SessionManager, reason: str) -> None:
        """Add completed/cancelled session to retention pool."""
        if len(self._retained) >= self._max_retained:
            oldest_id = next(iter(self._retained))
            del self._retained[oldest_id]
        self._retained[mgr.session_id] = RetainedSession(
            manager=mgr,
            ended_at_ms=time.time() * 1000,
            reason=reason,
        )

    def expire_inactive(self, now_ms: float, timeout_ms: float) -> list[str]:
        """Mark/remove retained sessions older than timeout. Returns IDs of expired sessions."""
        expired = []
        for session_id, retained in list(self._retained.items()):
            age = now_ms - retained.ended_at_ms
            if age >= timeout_ms:
                del self._retained[session_id]
                expired.append(session_id)
        return expired

    def get_retained_session(self, session_id: str) -> RetainedSession | None:
        """Retrieve retained terminal session for debugging/replay."""
        return self._retained.get(session_id)

    def list_retained(self) -> list[str]:
        """List all retained session IDs."""
        return list(self._retained.keys())

    def disconnect_session(self, session_id: str, timestamp_ms: float) -> ErrorMessage | None:
        """Clean up a session on disconnect: cancel active sessions, retain with 'disconnect' reason.

        Returns ErrorMessage if validation fails, None on success (idempotent for unknown/ended sessions).
        Only cancels and removes from active registry; never affects another session unless explicitly called with its ID.
        """
        if not session_id:
            return ErrorMessage(
                session_id=session_id,
                timestamp_ms=timestamp_ms,
                code=ErrorCode.INVALID_MESSAGE,
                detail="session_id cannot be empty",
            )

        mgr = self._sessions.get(session_id)
        if not mgr:
            # Idempotent: unknown or already-ended session
            return None

        mgr.cancel(CancelSession(session_id=session_id, timestamp_ms=timestamp_ms))
        self._retain_session(mgr, "disconnect")
        del self._sessions[session_id]
        return None

    def get_session(self, session_id: str) -> SessionManager:
        """Get session by ID; raises SessionNotFoundError if not found."""
        mgr = self._sessions.get(session_id)
        if not mgr:
            raise SessionNotFoundError(f"session {session_id} not found")
        return mgr

    def list_sessions(self) -> list[str]:
        """Return list of active session IDs."""
        return list(self._sessions.keys())

    def session_count(self) -> int:
        """Return number of active sessions."""
        return len(self._sessions)
