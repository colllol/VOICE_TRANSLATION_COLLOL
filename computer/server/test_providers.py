"""Provider-port tests for the replacement server."""
from computer.server.providers import FakeTranslationProvider


def test_fake_provider_has_explicit_capabilities_and_internal_text():
    provider = FakeTranslationProvider()

    result = provider.translate(b"audio", "vi", "en")

    assert result.audio.startswith(b"FAKE_AUDIO")
    assert result.transcript == "test utterance"
    assert result.translation.startswith("[vi->en]")
    assert provider.capabilities == {"asr": "fake", "nmt": "fake", "tts": "fake"}
