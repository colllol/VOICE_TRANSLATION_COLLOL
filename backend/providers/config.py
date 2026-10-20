"""Typed configuration for provider adapters with metadata."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProviderConfig:
    """Base provider configuration."""
    name: str
    model_revision: str
    license: str
    corpus: str
    supports_streaming: bool

    def validate(self) -> None:
        """Validate configuration is complete; raise ValueError if missing required fields."""
        if not self.name or not self.name.strip():
            raise ValueError("provider name must be non-empty")
        if not self.model_revision or not self.model_revision.strip():
            raise ValueError("model_revision must be non-empty")
        if not self.license or not self.license.strip():
            raise ValueError("license must be non-empty")
        if not self.corpus or not self.corpus.strip():
            raise ValueError("corpus must be non-empty")


@dataclass(frozen=True)
class ASRConfig(ProviderConfig):
    """Configuration for Automatic Speech Recognition provider."""
    pass


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

    def validate(self) -> None:
        super().validate()
        if not self.voice_id or not self.voice_id.strip():
            raise ValueError("voice_id must be non-empty")
