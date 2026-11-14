"""Server-owned session lifecycle for the computer rewrite."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from enum import Enum


class SessionState(str, Enum):
    ACTIVE = "active"
    DISCONNECTED_GRACE = "disconnected_grace"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass
class Session:
    session_id: str
    source_lang: str
    target_lang: str
    resume_token: str
    state: SessionState = SessionState.ACTIVE
    disconnected_at: float | None = None


class SessionCoordinator:
    def __init__(self, grace_seconds: float = 30.0) -> None:
        if grace_seconds <= 0:
            raise ValueError("grace_seconds must be positive")
        self.grace_seconds = grace_seconds
        self._sessions: dict[str, Session] = {}

    def start(self, source_lang: str, target_lang: str) -> Session:
        if not source_lang.strip() or not target_lang.strip():
            raise ValueError("language codes must be non-empty")
        session = Session(
            session_id=secrets.token_urlsafe(18),
            source_lang=source_lang,
            target_lang=target_lang,
            resume_token=secrets.token_urlsafe(32),
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise ValueError("session not found") from exc

    def disconnect(self, session_id: str) -> None:
        session = self.get(session_id)
        if session.state is SessionState.ACTIVE:
            session.state = SessionState.DISCONNECTED_GRACE
            session.disconnected_at = time.monotonic()

    def resume(self, session_id: str, resume_token: str) -> Session:
        session = self.get(session_id)
        if session.state is not SessionState.DISCONNECTED_GRACE:
            raise ValueError("session is not resumable")
        if not secrets.compare_digest(session.resume_token, resume_token):
            raise ValueError("invalid resume token")
        assert session.disconnected_at is not None
        if time.monotonic() - session.disconnected_at > self.grace_seconds:
            session.state = SessionState.CANCELLED
            raise ValueError("session is not resumable")
        session.state = SessionState.ACTIVE
        session.disconnected_at = None
        return session

    def cancel(self, session_id: str) -> None:
        session = self.get(session_id)
        if session.state not in (SessionState.CANCELLED, SessionState.COMPLETED):
            session.state = SessionState.CANCELLED
