"""Abstract base classes for provider adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from backend.providers.config import (
    ASRConfig,
    AudioFormat,
    NMTConfig,
    StreamingCapability,
    TTSConfig,
)


class ASRProvider(ABC):
    """Abstract ASR provider adapter."""

    def __init__(self, config: ASRConfig) -> None:
        config.validate()
        self.config = config

    @property
    def audio_format(self) -> Optional[AudioFormat]:
        return self.config.audio_format

    def require_audio_format(self) -> AudioFormat:
        if self.audio_format is None:
            raise ConfigError("audio format is not declared")
        return self.audio_format

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

    @property
    def audio_format(self) -> Optional[AudioFormat]:
        return self.config.audio_format

    def require_audio_format(self) -> AudioFormat:
        if self.audio_format is None:
            raise ConfigError("audio format is not declared")
        return self.audio_format

    @abstractmethod
    def synthesize(self, text: str, target_lang: str) -> bytes:
        """Synthesize text to audio bytes. Format depends on provider."""
        pass

    def streaming_declared(self) -> bool:
        """Metadata: provider declares streaming capability (not necessarily implemented)."""
        return self.config.streaming_declared

    @property
    def streaming_capability(self) -> StreamingCapability:
        """Expose declaration without implying a streaming method exists."""
        if self.config.streaming_declared:
            return StreamingCapability.DECLARED_NOT_IMPLEMENTED
        return StreamingCapability.NOT_DECLARED


class ProviderError(Exception):
    """Base exception for provider failures."""
    pass


class ConfigError(ProviderError):
    """Configuration is invalid or incomplete."""
    pass


class ProviderUnavailable(ProviderError):
    """Required provider credentials or model not available."""
    pass
