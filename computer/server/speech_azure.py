"""Azure public REST APIs for complete Vietnamese/English desktop utterances.

ASR: https://learn.microsoft.com/azure/ai-services/speech-service/rest-speech-to-text-short
NMT: https://learn.microsoft.com/azure/ai-services/translator/text-translation/reference/v3/translate
TTS: https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech
"""
from __future__ import annotations

import io
import json
import math
import re
import wave
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.client import HTTPException, HTTPSConnection
from typing import Any
from xml.etree import ElementTree

from computer.server.providers import ProviderConfigError, ProviderError, TranslationResult

_RATE = 16000
_CHANNELS = 1
_SAMPLE_BYTES = 2
_MAX_INPUT = 60 * _RATE * _SAMPLE_BYTES
_MAX_AUDIO_RESPONSE = 10 * 1024 * 1024
_MAX_JSON_RESPONSE = 256 * 1024
_KEY_HEADER = "Ocp-Apim-Subscription-Key"
_LANGUAGES = {
    "en": ("en-US", "en-US-JennyNeural"),
    "vi": ("vi-VN", "vi-VN-HoaiMyNeural"),
}
_ALIASES = {"en": "en", "en-us": "en", "vi": "vi", "vi-vn": "vi"}


@dataclass(frozen=True)
class AzureConfig:
    """Read COMPUTER_AZURE_{SPEECH,TRANSLATOR}_{KEY,REGION} after opt-in.

    Translator region may be omitted for a global Translator resource.
    COMPUTER_AZURE_TIMEOUT_SECONDS sets the socket timeout (default 10).
    """

    speech_region: str
    speech_key: str = field(repr=False)
    translator_key: str = field(repr=False)
    translator_region: str = ""
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> AzureConfig:
        return cls(
            speech_region=env.get("COMPUTER_AZURE_SPEECH_REGION", ""),
            speech_key=env.get("COMPUTER_AZURE_SPEECH_KEY", ""),
            translator_key=env.get("COMPUTER_AZURE_TRANSLATOR_KEY", ""),
            translator_region=env.get("COMPUTER_AZURE_TRANSLATOR_REGION", ""),
            timeout_seconds=_parse_timeout(env.get("COMPUTER_AZURE_TIMEOUT_SECONDS", "10")),
        )

    def __post_init__(self) -> None:
        if not _is_region(self.speech_region):
            raise ProviderConfigError("COMPUTER_AZURE_SPEECH_REGION must be an Azure region identifier")
        if self.translator_region and not _is_region(self.translator_region):
            raise ProviderConfigError("COMPUTER_AZURE_TRANSLATOR_REGION must be an Azure region identifier")
        for name, key in (("SPEECH", self.speech_key), ("TRANSLATOR", self.translator_key)):
            if not re.fullmatch(r"[!-~]+", key):
                raise ProviderConfigError(f"COMPUTER_AZURE_{name}_KEY must be a non-empty header value")
        if not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 60:
            raise ProviderConfigError("COMPUTER_AZURE_TIMEOUT_SECONDS must be greater than 0 and at most 60")


def _is_region(value: str) -> bool:
    return re.fullmatch(r"[a-z0-9]{1,63}", value) is not None


def _parse_timeout(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        raise ProviderConfigError("COMPUTER_AZURE_TIMEOUT_SECONDS must be a number") from None


class AzureTranslationProvider:
    """Blocking ASR -> NMT -> TTS; no streaming, fallback or speaker cloning.

    Input and output are raw PCM16LE mono at 16 kHz. Only call with one complete
    utterance (up to 60 seconds), not a transport frame. Audio and recognized text
    are sent to Azure. Returned text is internal and must not be sent on the wire.
    """

    capabilities = {"asr": "azure", "nmt": "azure", "tts": "azure"}

    def __init__(self, config: AzureConfig) -> None:
        self._config = config

    def translate(self, audio: bytes, source_lang: str, target_lang: str) -> TranslationResult:
        return self.translate_cancellable(audio, source_lang, target_lang, lambda: False)

    def translate_cancellable(
        self, audio: bytes, source_lang: str, target_lang: str, cancelled: Callable[[], bool],
    ) -> TranslationResult:
        def check_cancelled() -> None:
            if cancelled():
                raise ProviderError("translation cancelled")

        source = _ALIASES.get(source_lang.strip().lower())
        target = _ALIASES.get(target_lang.strip().lower())
        if source is None or target is None or source == target:
            raise ProviderError("Azure provider requires a Vietnamese/English language pair")
        if not audio or len(audio) % _SAMPLE_BYTES or len(audio) > _MAX_INPUT:
            raise ProviderError("Expected nonempty sample-aligned PCM16 audio up to 60 seconds")
        if audio.startswith(b"RIFF") and audio[8:12] == b"WAVE":
            raise ProviderError("Expected raw PCM16 audio, not a WAV container")

        check_cancelled()
        transcript = self._recognize(audio, _LANGUAGES[source][0])
        check_cancelled()
        translation = self._translate_text(transcript, source, target)
        check_cancelled()
        synthesized = self._synthesize(translation, *_LANGUAGES[target])
        check_cancelled()
        return TranslationResult(synthesized, transcript, translation)

    def _recognize(self, audio: bytes, locale: str) -> str:
        result = _decode_json("ASR", self._post(
            "ASR", f"{self._config.speech_region}.stt.speech.microsoft.com",
            f"/speech/recognition/conversation/cognitiveservices/v1?language={locale}&format=simple",
            _wrap_wav(audio),
            {_KEY_HEADER: self._config.speech_key, "Accept": "application/json",
             "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000"},
            _MAX_JSON_RESPONSE,
        ))
        if not isinstance(result, dict) or result.get("RecognitionStatus") != "Success":
            raise ProviderError("Azure ASR did not recognize speech")
        return _require_text("ASR", result.get("DisplayText"))

    def _translate_text(self, text: str, source: str, target: str) -> str:
        headers = {_KEY_HEADER: self._config.translator_key, "Content-Type": "application/json; charset=UTF-8"}
        if self._config.translator_region:
            headers["Ocp-Apim-Subscription-Region"] = self._config.translator_region
        result = _decode_json("NMT", self._post(
            "NMT", "api.cognitive.microsofttranslator.com",
            f"/translate?api-version=3.0&from={source}&to={target}",
            json.dumps([{"Text": text}], ensure_ascii=False).encode("utf-8"),
            headers, _MAX_JSON_RESPONSE,
        ))
        try:
            entry = result[0]["translations"][0]
            if entry["to"] == target:
                return _require_text("NMT", entry["text"])
        except (KeyError, IndexError, TypeError):
            pass
        raise ProviderError("Azure NMT returned an invalid translation")

    def _synthesize(self, text: str, locale: str, voice: str) -> bytes:
        ssml = ElementTree.Element("speak", {
            "version": "1.0", "xmlns": "http://www.w3.org/2001/10/synthesis", "xml:lang": locale,
        })
        ElementTree.SubElement(ssml, "voice", {"name": voice}).text = text
        wav = self._post(
            "TTS", f"{self._config.speech_region}.tts.speech.microsoft.com", "/cognitiveservices/v1",
            ElementTree.tostring(ssml, encoding="utf-8"),
            {_KEY_HEADER: self._config.speech_key, "Content-Type": "application/ssml+xml",
             "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm", "User-Agent": "collol-computer"},
            _MAX_AUDIO_RESPONSE,
        )
        return _unwrap_wav(wav)

    def _post(
        self, stage: str, host: str, path: str, body: bytes, headers: dict[str, str], limit: int
    ) -> bytes:
        # HTTPSConnection verifies TLS and does not follow redirects or load proxy credentials.
        connection = HTTPSConnection(host, timeout=self._config.timeout_seconds)
        try:
            connection.request("POST", path, body=body, headers=headers)
            with connection.getresponse() as response:
                if response.status != 200:
                    raise ProviderError(f"Azure {stage} failed (HTTP {response.status})")
                payload = response.read(limit + 1)
        except TimeoutError:
            raise ProviderError(f"Azure {stage} timed out") from None
        except (OSError, HTTPException):
            raise ProviderError(f"Azure {stage} connection failed") from None
        finally:
            connection.close()
        if len(payload) > limit:
            raise ProviderError(f"Azure {stage} response exceeded size limit")
        return payload


def _decode_json(stage: str, body: bytes) -> Any:
    try:
        return json.loads(body)
    except (ValueError, RecursionError):
        raise ProviderError(f"Azure {stage} returned invalid JSON") from None


def _require_text(stage: str, text: Any) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ProviderError(f"Azure {stage} returned no usable text")
    # Reject characters that cannot be included in the downstream UTF-8 SSML.
    if re.search(r"[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]", text):
        raise ProviderError(f"Azure {stage} returned invalid text")
    return text


def _wrap_wav(audio: bytes) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(_CHANNELS)
        wav.setsampwidth(_SAMPLE_BYTES)
        wav.setframerate(_RATE)
        wav.writeframes(audio)
    return output.getvalue()


def _unwrap_wav(body: bytes) -> bytes:
    try:
        with wave.open(io.BytesIO(body), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (_CHANNELS, _SAMPLE_BYTES, _RATE):
                raise ProviderError("Azure TTS returned an unexpected audio format")
            expected = wav.getnframes() * _SAMPLE_BYTES
            if not expected or expected > len(body):
                raise ProviderError("Azure TTS returned empty or truncated audio")
            audio = wav.readframes(wav.getnframes() + 1)
    except (wave.Error, EOFError):
        raise ProviderError("Azure TTS returned invalid WAV audio") from None
    if len(audio) != expected:
        raise ProviderError("Azure TTS returned invalid PCM audio")
    return audio