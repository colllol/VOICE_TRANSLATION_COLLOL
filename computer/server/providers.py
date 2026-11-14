"""Provider ports for the local replacement pipeline."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationResult:
    audio: bytes
    transcript: str
    translation: str


class FakeTranslationProvider:
    """Deterministic ASR -> NMT -> TTS stand-in for local integration tests."""

    capabilities = {"asr": "fake", "nmt": "fake", "tts": "fake"}

    def translate(self, audio: bytes, source_lang: str, target_lang: str) -> TranslationResult:
        if not audio:
            raise ValueError("audio must not be empty")
        if not source_lang.strip() or not target_lang.strip():
            raise ValueError("language codes must not be empty")
        transcript = "test utterance"
        translation = f"[{source_lang}->{target_lang}] TEST UTTERANCE"
        synthesized = b"FAKE_AUDIO" + bytes([len(translation), len(audio) & 0xFF]) * 32
        return TranslationResult(synthesized, transcript, translation)
