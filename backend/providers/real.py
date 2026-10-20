"""Real provider adapters for production use. Require explicit configuration."""
from __future__ import annotations

from backend.providers.base import ASRProvider, NMTProvider, TTSProvider, ConfigError
from backend.providers.config import ASRConfig, NMTConfig, TTSConfig


class RealASRProvider(ASRProvider):
    """Real ASR provider (e.g., Faster-Whisper). Requires model weights and config."""

    def __init__(self, config: ASRConfig) -> None:
        super().__init__(config)
        raise ConfigError(
            f"Real ASR provider '{config.name}' requires model weights and proper setup. "
            "Use fake providers for testing or configure real provider credentials."
        )

    def transcribe(self, audio_bytes: bytes) -> str:
        # Never reached; constructor always raises
        raise ConfigError("Real ASR provider not configured")


class RealNMTProvider(NMTProvider):
    """Real NMT provider (e.g., NLLB-200). Requires model weights and config."""

    def __init__(self, config: NMTConfig) -> None:
        super().__init__(config)
        raise ConfigError(
            f"Real NMT provider '{config.name}' requires model weights and proper setup. "
            "Use fake providers for testing or configure real provider credentials."
        )

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        # Never reached; constructor always raises
        raise ConfigError("Real NMT provider not configured")


class RealTTSProvider(TTSProvider):
    """Real TTS provider (e.g., Google Cloud Chirp 3). Requires API credentials."""

    def __init__(self, config: TTSConfig) -> None:
        super().__init__(config)
        raise ConfigError(
            f"Real TTS provider '{config.name}' requires API credentials and proper setup. "
            "Use fake providers for testing or configure real provider credentials."
        )

    def synthesize(self, text: str, target_lang: str) -> bytes:
        # Never reached; constructor always raises
        raise ConfigError("Real TTS provider not configured")
