import base64
from threading import Event

from fastapi.testclient import TestClient
import pytest

from computer.server.app import create_app
from computer.server.providers import ProviderError, TranslationResult
from computer.server.speech_azure import AzureConfig, AzureTranslationProvider
from computer.server.storage import SQLiteStore
from computer.server.test_session_transport import exchange, start, wait_for_state


def chunk(stream, seq, pcm):
    return {"stream_id": stream, "seq": seq, "data_b64": base64.b64encode(pcm).decode()}


def test_interleaved_chunks_translate_only_at_finish_and_keep_full_output(tmp_path):
    calls = []
    output = b"\x01\x02" * 2200

    class Provider:
        capabilities = {"tts": "test"}

        def translate(self, pcm, source, target):
            calls.append((pcm, source, target))
            return TranslationResult(output, "private transcript", "private translation")

    a, b = b"\x01\0" * 320, b"\x02\0" * 320
    with TestClient(create_app(tmp_path / "test.db", provider_factory=Provider)) as client:
        with client.websocket_connect("/ws") as ws:
            started = start(ws)
            sid = started["session_id"]
            assert started["payload"]["utterance_audio"] == "chunks-v1"
            for stream, seq, pcm in [("a2b", 0, a), ("b2a", 0, b), ("a2b", 1, b)]:
                assert exchange(ws, "utterance.chunk", chunk(stream, seq, pcm), sid)["type"] == "utterance.ack"
            assert not calls
            assert exchange(ws, "utterance.chunk", chunk("a2b", 1, a), sid)["type"] == "error"
            for stream in ("b2a", "a2b"):
                answer = exchange(ws, "utterance.finish", {"stream_id": stream}, sid)
                assert answer["type"] == "utterance.output"
                assert answer["payload"] == {"stream_id": stream, "data_b64": base64.b64encode(output).decode()}
            assert exchange(ws, "utterance.finish", {"stream_id": "a2b"}, sid)["type"] == "error"
            assert exchange(ws, "utterance.chunk", chunk("a2b", 2, a), sid)["type"] == "utterance.ack"
    assert calls == [(b, "en", "vi"), (a + b, "vi", "en")]


def test_pending_translation_is_discarded_on_cancel_or_disconnect(tmp_path):
    for disconnect in (False, True):
        entered, release, returning = Event(), Event(), Event()
        database = tmp_path / f"pending-{disconnect}.db"
        old_pcm = b"\x01\0" * 320
        new_pcm = b"\x02\0" * 320

        class Provider:
            capabilities = {"tts": "test"}

            def translate(self, pcm, source, target):
                if pcm == old_pcm:
                    entered.set()
                    assert release.wait(4)
                    returning.set()
                return TranslationResult(pcm, "private", "private")

        with TestClient(create_app(database, provider_factory=Provider)) as client:
            try:
                with client.websocket_connect("/ws") as ws:
                    sid = start(ws)["session_id"]
                    assert exchange(ws, "utterance.chunk", chunk("a2b", 0, old_pcm), sid)["type"] == "utterance.ack"
                    ws.send_json({"v": 1, "type": "utterance.finish", "message_id": "finish",
                                  "session_id": sid, "payload": {"stream_id": "a2b"}})
                    assert entered.wait(2)
                    if not disconnect:
                        assert exchange(ws, "session.cancel", {}, sid)["type"] == "session.cancelled"
                    else:
                        ws.close()
                    release.set()
                    assert returning.wait(2)
                    wait_for_state(SQLiteStore(database), sid, "cancelled")
                    if not disconnect:
                        new_sid = start(ws)["session_id"]
                        assert new_sid != sid
                        assert exchange(ws, "utterance.chunk", chunk("a2b", 0, new_pcm), new_sid)["type"] == "utterance.ack"
                        answer = exchange(ws, "utterance.finish", {"stream_id": "a2b"}, new_sid)
                        assert answer["session_id"] == new_sid
                        assert answer["payload"]["data_b64"] == base64.b64encode(new_pcm).decode()
            finally:
                release.set()


def test_azure_does_not_start_translation_after_cancel_during_recognition():
    stopped = Event()

    class Azure(AzureTranslationProvider):
        def _recognize(self, audio, locale):
            stopped.set()
            return "private"

        def _translate_text(self, text, source, target):
            pytest.fail("NMT must not start after cancellation")

    with pytest.raises(ProviderError, match="cancelled"):
        Azure(AzureConfig("test", "unused", "unused")).translate_cancellable(
            b"\x01\0", "vi", "en", stopped.is_set,
        )


def test_timeout_retires_session_before_accepting_another_chunk(tmp_path, monkeypatch):
    monkeypatch.setattr("computer.server.app.TRANSLATION_TIMEOUT_SECONDS", 0.1)
    release = Event()

    class Provider:
        capabilities = {"tts": "test"}

        def translate(self, pcm, source, target):
            release.wait(3)
            return TranslationResult(pcm, "private", "private")

    database = tmp_path / "timeout.db"
    with TestClient(create_app(database, provider_factory=Provider)) as client:
        try:
            with client.websocket_connect("/ws") as ws:
                sid = start(ws)["session_id"]
                pcm = b"\x01\0" * 320
                assert exchange(ws, "utterance.chunk", chunk("a2b", 0, pcm), sid)["type"] == "utterance.ack"
                result = exchange(ws, "utterance.finish", {"stream_id": "a2b"}, sid)
                assert result["message_id"] == "utterance.finish"
                assert result["payload"]["code"] == "translation_timeout"
                wait_for_state(SQLiteStore(database), sid, "cancelled")
                denied = exchange(ws, "utterance.chunk", chunk("a2b", 1, pcm), sid)
                assert denied["payload"]["code"] == "session_not_active"
        finally:
            release.set()
