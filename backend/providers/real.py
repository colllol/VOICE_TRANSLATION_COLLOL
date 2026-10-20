"""Real provider adapters for production use. Require explicit configuration."""
from __future__ import annotations

import os
from backend.providers.base import ASRProvider, NMTProvider, TTSProvider, ConfigError
from backend.providers.config import ASRConfig, NMTConfig, TTSConfig


class RealASRProvider(ASRProvider):
    """Real ASR provider (e.g., Faster-Whisper). Requires model weights and config."""

    def __init__(self, config: ASRConfig) -> None:
        super().__init__(config)
        self._model = None

    def transcribe(self, audio_bytes: bytes) -> str:
        raise ConfigError(
            f"Real ASR provider '{self.config.name}' requires model weights and proper setup. "
            "Use fake providers for testing or configure real provider credentials."
        )


class RealNMTProvider(NMTProvider):
    """Real NMT provider (e.g., NLLB-200). Requires model weights and config."""

    def __init__(self, config: NMTConfig) -> None:
        super().__init__(config)
        self._model = None

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        raise ConfigError(
            f"Real NMT provider '{self.config.name}' requires model weights and proper setup. "
            "Use fake providers for testing or configure real provider credentials."
        )


class RealTTSProvider(TTSProvider):
    """Real TTS provider (e.g., Google Cloud Chirp 3). Requires API credentials."""

    def __init__(self, config: TTSConfig) -> None:
        super().__init__(config)
        api_key = os.getenv("TTS_API_KEY")
        if not api_key:
            raise ConfigError(
                f"Real TTS provider '{self.config.name}' requires TTS_API_KEY environment variable. "
                "Use fake providers for testing or set credentials."
            )

    def synthesize(self, text: str, target_lang: str) -> bytes:
        raise ConfigError(
            f"Real TTS provider '{self.config.name}' requires API setup and credentials. "
            "Use fake providers for testing or configure real provider credentials."
        )
