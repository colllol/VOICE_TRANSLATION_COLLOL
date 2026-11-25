"""Provider ports for the local replacement pipeline."""
from __future__ import annotations

import os
import math
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TranslationResult:
    audio: bytes
    transcript: str
    translation: str


class ProviderConfigError(ValueError):
    """Provider selection or configuration is invalid."""


class ProviderError(RuntimeError):
    """An utterance could not be processed; message is safe for diagnostics."""


class TranslationProvider(Protocol):
    @property
    def capabilities(self) -> dict[str, str]: ...

    def translate(self, audio: bytes, source_lang: str, target_lang: str) -> TranslationResult: ...


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
        frequency = 440 if source_lang == "vi" else 660
        synthesized = b"".join(
            struct.pack("<h", round(2000 * math.sin(2 * math.pi * frequency * i / 16000)))
            for i in range(4000)
        )
        return TranslationResult(synthesized, transcript, translation)


def create_translation_provider(env: Mapping[str, str] | None = None) -> TranslationProvider:
    """Select fake by default or Azure via COMPUTER_TRANSLATION_PROVIDER=azure.

    An injected mapping replaces, rather than supplements, the process environment.
    """
    settings = os.environ if env is None else env
    selected = settings.get("COMPUTER_TRANSLATION_PROVIDER", "fake")
    if selected == "fake":
        return FakeTranslationProvider()
    if selected != "azure":
        raise ProviderConfigError("COMPUTER_TRANSLATION_PROVIDER must be fake or azure")

    from computer.server.speech_azure import AzureConfig, AzureTranslationProvider

    return AzureTranslationProvider(AzureConfig.from_env(settings))
