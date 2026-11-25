"""Provider-port tests for the replacement server."""
import io
import json
import wave
from xml.etree import ElementTree

import pytest

from computer.server.providers import (
    FakeTranslationProvider,
    ProviderConfigError,
    ProviderError,
    create_translation_provider,
)


def test_fake_provider_has_explicit_capabilities_and_internal_text():
    provider = FakeTranslationProvider()

    result = provider.translate(b"audio", "vi", "en")

    assert len(result.audio) == 8000 and any(result.audio)
    assert result.transcript == "test utterance"
    assert result.translation.startswith("[vi->en]")
    assert provider.capabilities == {"asr": "fake", "nmt": "fake", "tts": "fake"}


PCM = b"\xff\x00\x01\x80" * 160
AZURE_ENV = {
    "COMPUTER_TRANSLATION_PROVIDER": "azure",
    "COMPUTER_AZURE_SPEECH_REGION": "southeastasia",
    "COMPUTER_AZURE_SPEECH_KEY": "fixture-speech-not-a-credential",
    "COMPUTER_AZURE_TRANSLATOR_REGION": "eastus",
    "COMPUTER_AZURE_TRANSLATOR_KEY": "fixture-translator-not-a-credential",
    "COMPUTER_AZURE_TIMEOUT_SECONDS": "3.5",
}


def wav_bytes(pcm, rate=16000):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        wav.writeframes(pcm)
    return output.getvalue()


@pytest.fixture
def https_stub(monkeypatch):
    from computer.server import speech_azure

    requests, replies = [], []

    class Response(io.BytesIO):
        def __init__(self, status, body):
            super().__init__(body)
            self.status = status

    class Connection:
        def __init__(self, host, *, timeout):
            self.host = host
            self.timeout = timeout

        def request(self, method, path, body, headers):
            requests.append((self.host, self.timeout, method, path, body, headers))

        def getresponse(self):
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            status, body = reply
            return Response(status, body)

        def close(self):
            pass

    monkeypatch.setattr(speech_azure, "HTTPSConnection", Connection)
    return requests, replies


def json_reply(value):
    return 200, json.dumps(value, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize(
    "source,target,source_locale,target_locale,voice,transcript,translation",
    [
        ("vi", "en-US", "vi-VN", "en-US", "en-US-JennyNeural", "Xin ch\u00e0o", "Hello & <friends>"),
        ("en", "vi-VN", "en-US", "vi-VN", "vi-VN-HoaiMyNeural", "Hello", "Xin ch\u00e0o"),
    ],
)
def test_azure_utterance_round_trip(
    https_stub, source, target, source_locale, target_locale, voice, transcript, translation
):
    requests, replies = https_stub
    replies.extend([
        json_reply({"RecognitionStatus": "Success", "DisplayText": transcript}),
        json_reply([{"translations": [{"to": target[:2], "text": translation}]}]),
        (200, wav_bytes(PCM)),
    ])

    provider = create_translation_provider(AZURE_ENV)
    result = provider.translate(PCM, source, target)

    assert provider.capabilities == {"asr": "azure", "nmt": "azure", "tts": "azure"}
    assert (result.audio, result.transcript, result.translation) == (PCM, transcript, translation)
    assert not replies
    asr, nmt, tts = requests
    assert [request[1:3] for request in requests] == [(3.5, "POST")] * 3
    assert asr[0] == "southeastasia.stt.speech.microsoft.com"
    assert asr[3] == f"/speech/recognition/conversation/cognitiveservices/v1?language={source_locale}&format=simple"
    assert asr[5]["Ocp-Apim-Subscription-Key"] == AZURE_ENV["COMPUTER_AZURE_SPEECH_KEY"]
    assert asr[5]["Content-Type"] == "audio/wav; codecs=audio/pcm; samplerate=16000"
    with wave.open(io.BytesIO(asr[4])) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
        assert wav.readframes(wav.getnframes()) == PCM
    assert nmt[0] == "api.cognitive.microsofttranslator.com"
    assert nmt[3] == f"/translate?api-version=3.0&from={source[:2]}&to={target[:2]}"
    assert nmt[5]["Ocp-Apim-Subscription-Key"] == AZURE_ENV["COMPUTER_AZURE_TRANSLATOR_KEY"]
    assert nmt[5]["Ocp-Apim-Subscription-Region"] == "eastus"
    assert json.loads(nmt[4]) == [{"Text": transcript}]
    assert tts[0] == "southeastasia.tts.speech.microsoft.com"
    assert tts[3] == "/cognitiveservices/v1"
    assert tts[5]["Ocp-Apim-Subscription-Key"] == AZURE_ENV["COMPUTER_AZURE_SPEECH_KEY"]
    assert tts[5]["X-Microsoft-OutputFormat"] == "riff-16khz-16bit-mono-pcm"
    ssml = ElementTree.fromstring(tts[4])
    assert ssml.attrib["{http://www.w3.org/XML/1998/namespace}lang"] == target_locale
    assert len(ssml) == 1 and ssml[0].attrib["name"] == voice and ssml[0].text == translation


def test_factory_does_not_read_azure_settings_without_opt_in():
    class SelectionOnly(dict):
        def get(self, key, default=None):
            assert key == "COMPUTER_TRANSLATION_PROVIDER"
            return super().get(key, default)

    assert isinstance(create_translation_provider(SelectionOnly()), FakeTranslationProvider)
    assert isinstance(create_translation_provider(SelectionOnly(COMPUTER_TRANSLATION_PROVIDER="fake")),
                      FakeTranslationProvider)
    with pytest.raises(ProviderConfigError, match="must be fake or azure"):
        create_translation_provider(SelectionOnly(COMPUTER_TRANSLATION_PROVIDER="unsupported"))


@pytest.mark.parametrize("name,value", [
    ("SPEECH_REGION", "eastus.example.invalid"),
    ("SPEECH_KEY", ""),
    ("TRANSLATOR_KEY", "fixture\r\nHeader: value"),
    ("TRANSLATOR_REGION", "us east"),
    ("TIMEOUT_SECONDS", "invalid"),
    ("TIMEOUT_SECONDS", "nan"),
    ("TIMEOUT_SECONDS", "0"),
    ("TIMEOUT_SECONDS", "61"),
])
def test_invalid_config_never_connects(https_stub, name, value):
    key = f"COMPUTER_AZURE_{name}"
    with pytest.raises(ProviderConfigError, match=key):
        create_translation_provider({**AZURE_ENV, key: value})
    assert https_stub[0] == []


def test_config_representation_omits_keys():
    from computer.server.speech_azure import AzureConfig

    config = AzureConfig.from_env(AZURE_ENV)
    assert all(value not in repr(config) for name, value in AZURE_ENV.items() if name.endswith("_KEY"))


@pytest.mark.parametrize("audio,source,target", [
    (b"", "vi", "en"),
    (b"\x00", "vi", "en"),
    (bytes(60 * 16000 * 2 + 2), "vi", "en"),
    (PCM, "fr", "en"),
    (PCM, "vi", "vi-VN"),
    (wav_bytes(PCM), "vi", "en"),
], ids=["empty", "unaligned", "over-limit", "unsupported-language", "same-language", "wav-wrapper"])
def test_invalid_utterance_never_connects(https_stub, audio, source, target):
    provider = create_translation_provider(AZURE_ENV)
    with pytest.raises(ProviderError):
        provider.translate(audio, source, target)
    assert https_stub[0] == []


ASR_OK = json_reply({"RecognitionStatus": "Success", "DisplayText": "PRIVATE-FIXTURE"})
NMT_OK = json_reply([{"translations": [{"to": "en", "text": "PRIVATE-FIXTURE"}]}])


@pytest.mark.parametrize("prior,reply,error", [
    ([], TimeoutError("PRIVATE-FIXTURE"), "ASR timed out"),
    ([], OSError("PRIVATE-FIXTURE"), "ASR connection failed"),
    ([], (302, b"PRIVATE-FIXTURE"), "ASR failed (HTTP 302)"),
    ([], (200, b"PRIVATE-FIXTURE"), "ASR returned invalid JSON"),
    ([], (200, b"x" * (256 * 1024 + 1)), "ASR response exceeded size limit"),
    ([], json_reply({"RecognitionStatus": "NoMatch", "DisplayText": "PRIVATE-FIXTURE"}),
     "ASR did not recognize speech"),
    ([], json_reply({"RecognitionStatus": "Success", "DisplayText": " "}), "ASR returned no usable text"),
    ([ASR_OK], (401, b"PRIVATE-FIXTURE"), "NMT failed (HTTP 401)"),
    ([ASR_OK], json_reply([]), "NMT returned an invalid translation"),
    ([ASR_OK], json_reply([{"translations": [{"to": "vi", "text": "PRIVATE-FIXTURE"}]}]),
     "NMT returned an invalid translation"),
    ([ASR_OK], json_reply([{"translations": [{"to": "en", "text": "\u0000"}]}]),
     "NMT returned invalid text"),
    ([ASR_OK, NMT_OK], (429, b"PRIVATE-FIXTURE"), "TTS failed (HTTP 429)"),
    ([ASR_OK, NMT_OK], (200, b"PRIVATE-FIXTURE"), "TTS returned invalid WAV audio"),
    ([ASR_OK, NMT_OK], (200, wav_bytes(PCM, rate=24000)), "TTS returned an unexpected audio format"),
    ([ASR_OK, NMT_OK], (200, wav_bytes(PCM)[:-4]), "TTS returned invalid PCM audio"),
    ([ASR_OK, NMT_OK], (200, wav_bytes(b"")), "TTS returned empty or truncated audio"),
])
def test_provider_stops_at_failed_stage_without_exposing_payload(https_stub, capsys, caplog, prior, reply, error):
    requests, replies = https_stub
    replies.extend([*prior, reply])
    provider = create_translation_provider(AZURE_ENV)

    with pytest.raises(ProviderError) as exc:
        provider.translate(PCM, "vi", "en")

    assert str(exc.value) == f"Azure {error}"
    assert len(requests) == len(prior) + 1
    assert not replies
    assert capsys.readouterr() == ("", "")
    assert caplog.text == ""


def test_global_translator_omits_region_header(https_stub):
    requests, replies = https_stub
    replies.extend([ASR_OK, NMT_OK, (200, wav_bytes(PCM))])
    env = {key: value for key, value in AZURE_ENV.items()
           if key not in {"COMPUTER_AZURE_TRANSLATOR_REGION", "COMPUTER_AZURE_TIMEOUT_SECONDS"}}

    create_translation_provider(env).translate(PCM, "vi", "en")

    assert "Ocp-Apim-Subscription-Region" not in requests[1][5]
    assert [request[1] for request in requests] == [10.0] * 3
