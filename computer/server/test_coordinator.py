"""Lifecycle tests for the replacement server coordinator."""
import pytest

from computer.server.coordinator import SessionCoordinator, SessionState


def test_server_allocates_session_and_enters_active_state():
    coordinator = SessionCoordinator(grace_seconds=30)

    session = coordinator.start("vi", "en")

    assert session.session_id
    assert session.state is SessionState.ACTIVE
    assert session.source_lang == "vi"
    assert session.target_lang == "en"


def test_disconnect_enters_grace_and_resume_restores_active():
    coordinator = SessionCoordinator(grace_seconds=30)
    session = coordinator.start("vi", "en")

    coordinator.disconnect(session.session_id)
    resumed = coordinator.resume(session.session_id, session.resume_token)

    assert resumed.session_id == session.session_id
    assert resumed.state is SessionState.ACTIVE


def test_cancel_is_terminal_and_idempotent():
    coordinator = SessionCoordinator(grace_seconds=30)
    session = coordinator.start("vi", "en")

    coordinator.cancel(session.session_id)
    coordinator.cancel(session.session_id)

    assert coordinator.get(session.session_id).state is SessionState.CANCELLED
    with pytest.raises(ValueError, match="not resumable"):
        coordinator.resume(session.session_id, session.resume_token)
