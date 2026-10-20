"""Abstract base classes for provider adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, List

from backend.providers.config import ASRConfig, NMTConfig, TTSConfig


class ASRProvider(ABC):
    """Abstract ASR provider adapter."""

    def __init__(self, config: ASRConfig) -> None:
        config.validate()
        self.config = config

    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio to text. Internal to backend; not exposed in protocol."""
        pass


class NMTProvider(ABC):
    """Abstract NMT provider adapter."""

    def __init__(self, config: NMTConfig) -> None:
        config.validate()
        self.config = config

    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text. Internal to backend; not exposed in protocol."""
        pass


class TTSProvider(ABC):
    """Abstract TTS provider adapter."""

    def __init__(self, config: TTSConfig) -> None:
        config.validate()
        self.config = config

    @abstractmethod
    def synthesize(self, text: str, target_lang: str) -> bytes:
        """Synthesize text to audio bytes. Format depends on provider."""
        pass

    def streaming_declared(self) -> bool:
        """Metadata: provider declares streaming capability (not necessarily implemented)."""
        return self.config.streaming_declared


class ProviderError(Exception):
    """Base exception for provider failures."""
    pass


class ConfigError(ProviderError):
    """Configuration is invalid or incomplete."""
    pass


class ProviderUnavailable(ProviderError):
    """Required provider credentials or model not available."""
    pass
