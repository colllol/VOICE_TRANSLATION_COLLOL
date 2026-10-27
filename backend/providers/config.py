"""Typed configuration for provider adapters with metadata."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AudioSampleFormat(str, Enum):
    """Concrete PCM encodings understood by the provider boundary."""

    PCM_S16LE = "pcm_s16le"


@dataclass(frozen=True)
class AudioFormat:
    """Complete PCM metadata; compressed/opaque provider formats need another contract."""

    sample_rate_hz: int
    channels: int
    sample_format: AudioSampleFormat

    def __post_init__(self) -> None:
        if not isinstance(self.sample_rate_hz, int) or self.sample_rate_hz <= 0:
            raise ValueError("audio sample rate must be positive")
        if not isinstance(self.channels, int) or self.channels <= 0:
            raise ValueError("audio channel count must be positive")
        if not isinstance(self.sample_format, AudioSampleFormat):
            raise ValueError("audio sample format must be a supported AudioSampleFormat")


class StreamingCapability(str, Enum):
    """Declaration metadata, not a promise that the adapter exposes stream methods."""

    NOT_DECLARED = "not_declared"
    DECLARED_NOT_IMPLEMENTED = "declared_not_implemented"


@dataclass(frozen=True)
class ProviderConfig:
    """Base provider configuration."""
    name: str
    model_revision: str
    license: str
    corpus: str
    streaming_declared: bool

    def validate(self) -> None:
        """Validate configuration is complete; raise ValueError if missing required fields."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("provider name must be non-empty string")
        if not isinstance(self.model_revision, str) or not self.model_revision.strip():
            raise ValueError("model_revision must be non-empty string")
        if not isinstance(self.license, str) or not self.license.strip():
            raise ValueError("license must be non-empty string (reference-only metadata)")
        if not isinstance(self.corpus, str) or not self.corpus.strip():
            raise ValueError("corpus must be non-empty string (reference-only metadata)")
        if not isinstance(self.streaming_declared, bool):
            raise ValueError("streaming_declared must be boolean")


@dataclass(frozen=True)
class ASRConfig(ProviderConfig):
    """Configuration for Automatic Speech Recognition provider."""
    audio_format: Optional[AudioFormat] = None

    def validate(self) -> None:
        super().validate()
        if self.audio_format is not None and not isinstance(self.audio_format, AudioFormat):
            raise ValueError("audio_format must be an AudioFormat or None")


@dataclass(frozen=True)
class NMTConfig(ProviderConfig):
    """Configuration for Neural Machine Translation provider."""
    max_tokens: int = 512

    def validate(self) -> None:
        super().validate()
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")


@dataclass(frozen=True)
class TTSConfig(ProviderConfig):
    """Configuration for Text-to-Speech provider."""
    voice_id: str = "default"
    audio_format: Optional[AudioFormat] = None

    def validate(self) -> None:
        super().validate()
        if not self.voice_id or not self.voice_id.strip():
            raise ValueError("voice_id must be non-empty")
        if self.audio_format is not None and not isinstance(self.audio_format, AudioFormat):
            raise ValueError("audio_format must be an AudioFormat or None")
