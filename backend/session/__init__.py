"""Session service boundary for VT-002 protocol contract."""
from backend.session.service import SessionService, SessionNotFoundError

__all__ = ["SessionService", "SessionNotFoundError"]
