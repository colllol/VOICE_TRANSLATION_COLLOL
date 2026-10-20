"""Deterministic fake providers for testing duplex pipeline contract."""
from __future__ import annotations

from backend.providers.base import ASRProvider, NMTProvider, TTSProvider, ProviderError
from backend.providers.config import ASRConfig, NMTConfig, TTSConfig


class FakeASRProvider(ASRProvider):
    """Deterministic ASR for testing; transcribes synthetic audio to predictable text."""

    def transcribe(self, audio_bytes: bytes) -> str:
        """Mock transcription: return length-based deterministic text."""
        if not audio_bytes:
            raise ProviderError("empty audio payload")

        length = len(audio_bytes)
        count = max(1, length // 100)

        return f"test utterance {count}".strip()


class FakeNMTProvider(NMTProvider):
    """Deterministic NMT for testing; translates text by reversing + lang tag."""

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Mock translation: uppercase + language tags for determinism."""
        if not text:
            raise ProviderError("empty text")
        if not source_lang or not target_lang:
            raise ProviderError("missing language codes")

        reversed_text = " ".join(reversed(text.split()))
        return f"[{source_lang}→{target_lang}] {reversed_text.upper()}"


class FakeTTSProvider(TTSProvider):
    """Deterministic TTS for testing; synthesizes mock audio with header."""

    def synthesize(self, text: str, target_lang: str) -> bytes:
        """Mock synthesis: return PCM header + text length as samples."""
        if not text:
            raise ProviderError("empty text for synthesis")
        if not target_lang:
            raise ProviderError("missing target language")

        text_len = len(text)
        audio_samples = text_len * 100

        header = b"FAKE_PCM"
        body = bytes([audio_samples & 0xFF, (audio_samples >> 8) & 0xFF]) * 10

        return header + body


def create_fake_providers() -> tuple[FakeASRProvider, FakeNMTProvider, FakeTTSProvider]:
    """Create a complete set of fake providers for testing."""
    asr_config = ASRConfig(
        name="fake-asr",
        model_revision="test-v1",
        license="MIT",
        corpus="synthetic",
        supports_streaming=True,
    )

    nmt_config = NMTConfig(
        name="fake-nmt",
        model_revision="test-v1",
        license="MIT",
        corpus="synthetic",
        supports_streaming=False,
        max_tokens=512,
    )

    tts_config = TTSConfig(
        name="fake-tts",
        model_revision="test-v1",
        license="MIT",
        corpus="synthetic",
        supports_streaming=True,
        voice_id="fake-voice-1",
    )

    return (
        FakeASRProvider(asr_config),
        FakeNMTProvider(nmt_config),
        FakeTTSProvider(tts_config),
    )
