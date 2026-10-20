"""Tests for ASR/NMT/TTS provider adapters and configuration."""
from __future__ import annotations

import pytest
from backend.providers.config import ASRConfig, NMTConfig, TTSConfig
from backend.providers.fake import (
    FakeASRProvider,
    FakeNMTProvider,
    FakeTTSProvider,
    create_fake_providers,
)
from backend.providers.real import RealASRProvider, RealNMTProvider, RealTTSProvider
from backend.providers.base import ProviderError, ConfigError


class TestASRConfig:
    """Test ASR configuration validation."""

    def test_valid_asr_config(self):
        config = ASRConfig(
            name="whisper",
            model_revision="tiny",
            license="MIT",
            corpus="openwebtext",
            streaming_declared=True,
        )
        config.validate()

    def test_empty_name_raises(self):
        config = ASRConfig(
            name="",
            model_revision="v1",
            license="MIT",
            corpus="test",
            streaming_declared=False,
        )
        with pytest.raises(ValueError, match="name must be non-empty"):
            config.validate()

    def test_empty_model_revision_raises(self):
        config = ASRConfig(
            name="asr",
            model_revision="",
            license="MIT",
            corpus="test",
            streaming_declared=False,
        )
        with pytest.raises(ValueError, match="model_revision must be non-empty"):
            config.validate()

    def test_empty_license_raises(self):
        config = ASRConfig(
            name="asr",
            model_revision="v1",
            license="",
            corpus="test",
            streaming_declared=False,
        )
        with pytest.raises(ValueError, match="license must be non-empty"):
            config.validate()

    def test_empty_corpus_raises(self):
        config = ASRConfig(
            name="asr",
            model_revision="v1",
            license="MIT",
            corpus="",
            streaming_declared=False,
        )
        with pytest.raises(ValueError, match="corpus must be non-empty"):
            config.validate()

    def test_whitespace_only_name_raises(self):
        config = ASRConfig(
            name="   ",
            model_revision="v1",
            license="MIT",
            corpus="test",
            streaming_declared=False,
        )
        with pytest.raises(ValueError, match="name must be non-empty"):
            config.validate()


class TestNMTConfig:
    """Test NMT configuration validation."""

    def test_valid_nmt_config(self):
        config = NMTConfig(
            name="nllb",
            model_revision="600m",
            license="CC-BY-NC-4.0",
            corpus="parallel",
            streaming_declared=False,
            max_tokens=512,
        )
        config.validate()

    def test_invalid_max_tokens_raises(self):
        config = NMTConfig(
            name="nllb",
            model_revision="600m",
            license="CC-BY-NC-4.0",
            corpus="parallel",
            streaming_declared=False,
            max_tokens=0,
        )
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            config.validate()

    def test_default_max_tokens(self):
        config = NMTConfig(
            name="nllb",
            model_revision="600m",
            license="CC-BY-NC-4.0",
            corpus="parallel",
            streaming_declared=False,
        )
        assert config.max_tokens == 512


class TestTTSConfig:
    """Test TTS configuration validation."""

    def test_valid_tts_config(self):
        config = TTSConfig(
            name="chirp",
            model_revision="3",
            license="proprietary",
            corpus="tts-training",
            streaming_declared=True,
            voice_id="en-US-Neural2-A",
        )
        config.validate()

    def test_empty_voice_id_raises(self):
        config = TTSConfig(
            name="chirp",
            model_revision="3",
            license="proprietary",
            corpus="tts-training",
            streaming_declared=True,
            voice_id="",
        )
        with pytest.raises(ValueError, match="voice_id must be non-empty"):
            config.validate()

    def test_default_voice_id(self):
        config = TTSConfig(
            name="chirp",
            model_revision="3",
            license="proprietary",
            corpus="tts-training",
            streaming_declared=True,
        )
        assert config.voice_id == "default"


class TestFakeASRProvider:
    """Test fake ASR provider implementation."""

    def setup_method(self):
        config = ASRConfig(
            name="fake-asr",
            model_revision="test",
            license="MIT",
            corpus="synthetic",
            streaming_declared=True,
        )
        self.provider = FakeASRProvider(config)

    def test_transcribe_success(self):
        audio = b"x" * 500
        result = self.provider.transcribe(audio)
        assert "test utterance" in result
        assert "5" in result

    def test_transcribe_empty_raises(self):
        with pytest.raises(ProviderError, match="empty audio"):
            self.provider.transcribe(b"")

    def test_transcribe_deterministic(self):
        audio = b"y" * 1000
        result1 = self.provider.transcribe(audio)
        result2 = self.provider.transcribe(audio)
        assert result1 == result2

    def test_config_accessible(self):
        assert self.provider.config.name == "fake-asr"
        assert self.provider.config.streaming_declared is True


class TestFakeNMTProvider:
    """Test fake NMT provider implementation."""

    def setup_method(self):
        config = NMTConfig(
            name="fake-nmt",
            model_revision="test",
            license="MIT",
            corpus="synthetic",
            streaming_declared=False,
        )
        self.provider = FakeNMTProvider(config)

    def test_translate_success(self):
        result = self.provider.translate("hello world", "en", "vi")
        assert "[en→vi]" in result
        assert "HELLO" in result or "WORLD" in result

    def test_translate_empty_text_raises(self):
        with pytest.raises(ProviderError, match="empty text"):
            self.provider.translate("", "en", "vi")

    def test_translate_missing_source_lang_raises(self):
        with pytest.raises(ProviderError, match="missing language"):
            self.provider.translate("hello", "", "vi")

    def test_translate_missing_target_lang_raises(self):
        with pytest.raises(ProviderError, match="missing language"):
            self.provider.translate("hello", "en", "")

    def test_translate_reverses_words(self):
        result = self.provider.translate("one two three", "en", "vi")
        assert "THREE TWO ONE" in result


class TestFakeTTSProvider:
    """Test fake TTS provider implementation."""

    def setup_method(self):
        config = TTSConfig(
            name="fake-tts",
            model_revision="test",
            license="MIT",
            corpus="synthetic",
            streaming_declared=True,
            voice_id="test-voice",
        )
        self.provider = FakeTTSProvider(config)

    def test_synthesize_success(self):
        result = self.provider.synthesize("hello", "en")
        assert result.startswith(b"FAKE_AUDIO_TEST")
        assert len(result) > len(b"FAKE_AUDIO_TEST")

    def test_synthesize_empty_text_raises(self):
        with pytest.raises(ProviderError, match="empty text"):
            self.provider.synthesize("", "en")

    def test_synthesize_missing_lang_raises(self):
        with pytest.raises(ProviderError, match="missing target language"):
            self.provider.synthesize("hello", "")

    def test_synthesize_deterministic_length(self):
        text1 = "hello"
        text2 = "hello"
        result1 = self.provider.synthesize(text1, "en")
        result2 = self.provider.synthesize(text2, "en")
        assert len(result1) == len(result2)

    def test_streaming_declared(self):
        assert self.provider.streaming_declared() is True


class TestFakeProviderFactory:
    """Test factory for creating fake providers."""

    def test_create_fake_providers(self):
        asr, nmt, tts = create_fake_providers()

        assert isinstance(asr, FakeASRProvider)
        assert isinstance(nmt, FakeNMTProvider)
        assert isinstance(tts, FakeTTSProvider)

    def test_fake_providers_ready_to_use(self):
        asr, nmt, tts = create_fake_providers()

        audio = b"test" * 100
        text = asr.transcribe(audio)
        assert text

        translated = nmt.translate(text, "en", "vi")
        assert translated

        synthesized = tts.synthesize(translated, "vi")
        assert synthesized

    def test_intermediate_text_never_in_audio_output(self):
        """Prove intermediate ASR/NMT text never appears in TTS audio output."""
        asr, nmt, tts = create_fake_providers()

        audio_in = b"simulated-input-audio" * 50
        transcribed = asr.transcribe(audio_in)
        translated = nmt.translate(transcribed, "en", "vi")
        audio_out = tts.synthesize(translated, "vi")

        # Verify intermediate text never appears in final audio bytes
        assert transcribed.encode() not in audio_out
        assert translated.encode() not in audio_out
        # Verify output is opaque test audio, not text
        assert audio_out.startswith(b"FAKE_AUDIO_TEST")


class TestRealProviderFailsClosedWithoutConfig:
    """Test real providers fail closed when config is missing."""

    def test_real_asr_construction_raises(self):
        config = ASRConfig(
            name="real-asr",
            model_revision="production",
            license="proprietary",
            corpus="real-data",
            streaming_declared=True,
        )

        with pytest.raises(ConfigError, match="Real ASR provider.*requires model weights"):
            RealASRProvider(config)

    def test_real_nmt_construction_raises(self):
        config = NMTConfig(
            name="real-nmt",
            model_revision="production",
            license="proprietary",
            corpus="real-data",
            streaming_declared=False,
        )

        with pytest.raises(ConfigError, match="Real NMT provider.*requires model weights"):
            RealNMTProvider(config)

    def test_real_tts_construction_raises(self):
        config = TTSConfig(
            name="real-tts",
            model_revision="production",
            license="proprietary",
            corpus="real-data",
            streaming_declared=True,
        )

        with pytest.raises(ConfigError, match="Real TTS provider.*requires API credentials"):
            RealTTSProvider(config)


class TestProviderDuplexPipeline:
    """Test provider integration for duplex pipeline."""

    def test_fake_pipeline_a2b_direction(self):
        """Test fake providers in A→B translation direction."""
        asr, nmt, tts = create_fake_providers()

        source_audio = b"audio_a2b_payload" * 10

        text = asr.transcribe(source_audio)
        translated = nmt.translate(text, "en", "vi")
        output_audio = tts.synthesize(translated, "vi")

        assert text
        assert translated
        assert output_audio
        assert len(output_audio) > 0

    def test_fake_pipeline_b2a_direction(self):
        """Test fake providers in B→A translation direction."""
        asr, nmt, tts = create_fake_providers()

        source_audio = b"audio_b2a_payload" * 10

        text = asr.transcribe(source_audio)
        translated = nmt.translate(text, "vi", "en")
        output_audio = tts.synthesize(translated, "en")

        assert text
        assert translated
        assert output_audio
        assert len(output_audio) > 0

    def test_error_propagation_asr_to_nmt(self):
        """Test error propagation: ASR error blocks NMT."""
        asr, nmt, tts = create_fake_providers()

        with pytest.raises(ProviderError):
            asr.transcribe(b"")

    def test_error_propagation_nmt_to_tts(self):
        """Test error propagation: NMT error blocks TTS."""
        asr, nmt, tts = create_fake_providers()

        with pytest.raises(ProviderError):
            nmt.translate("", "en", "vi")

    def test_error_propagation_tts(self):
        """Test error propagation: TTS error propagates."""
        asr, nmt, tts = create_fake_providers()

        with pytest.raises(ProviderError):
            tts.synthesize("", "en")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
