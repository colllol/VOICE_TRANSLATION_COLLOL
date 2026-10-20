"""Smoke test: providers integrated with session service and message flow.

Note: This test requires protocol and backend.session modules to be available.
If those modules are not in scope, this test will be skipped.
"""
from __future__ import annotations

try:
    from protocol.messages import SessionStart, AudioChunk, SessionEnd, Direction
    from backend.session.service import SessionService
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False

from backend.providers.fake import create_fake_providers

import pytest

pytestmark = pytest.mark.skipif(
    not INTEGRATION_AVAILABLE,
    reason="protocol and session modules required for integration smoke test"
)


def test_session_with_fake_providers():
    """Complete flow: session + audio chunks + fake providers."""
    svc = SessionService()
    asr, nmt, tts = create_fake_providers()

    session_id = "s1"

    msg = SessionStart(session_id, 1000, "en", "vi")
    err = svc.start_session(msg)
    assert err is None

    source_audio_a2b = b"english_audio" * 20
    chunk_a2b = AudioChunk(session_id, Direction.A_TO_B, 0, 1100, source_audio_a2b, is_final=False)
    err = svc.process_audio_chunk(chunk_a2b)
    assert err is None

    text = asr.transcribe(source_audio_a2b)
    assert text

    translated = nmt.translate(text, "en", "vi")
    assert translated

    synth_audio = tts.synthesize(translated, "vi")
    assert synth_audio

    chunk_b2a = AudioChunk(session_id, Direction.B_TO_A, 0, 1200, synth_audio, is_final=False)
    err = svc.process_audio_chunk(chunk_b2a)
    assert err is None

    msg = SessionEnd(session_id, 1300)
    err = svc.end_session(msg)
    assert err is None

    assert svc.session_count() == 0


def test_multiple_providers_independent():
    """Multiple provider instances can coexist."""
    asr1, nmt1, tts1 = create_fake_providers()
    asr2, nmt2, tts2 = create_fake_providers()

    audio = b"test" * 100
    text1 = asr1.transcribe(audio)
    text2 = asr2.transcribe(audio)

    assert text1 == text2


if __name__ == "__main__":
    if not INTEGRATION_AVAILABLE:
        print("⚠ Skipped: protocol and session modules not available")
    else:
        test_session_with_fake_providers()
        test_multiple_providers_independent()
        print("✓ providers smoke tests passed")
