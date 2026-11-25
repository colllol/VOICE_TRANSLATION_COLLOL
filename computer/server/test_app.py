"""Replacement server transport tests."""
import base64
from contextlib import closing
import sqlite3

import pytest

from fastapi.testclient import TestClient

from computer.server.app import create_app


def frame_payload(seq: int = 0) -> dict:
    return {
        "stream_id": "a2b",
        "seq": seq,
        "capture_time_ms": seq * 20,
        "duration_ms": 20,
        "data_b64": base64.b64encode(bytes(640)).decode("ascii"),
    }


def exchange(ws, command: str, payload: dict, session_id: str | None = None) -> dict:
    message = {"v": 1, "type": command, "message_id": command, "payload": payload}
    if session_id is not None:
        message["session_id"] = session_id
    ws.send_json(message)
    return ws.receive_json()


def start(ws) -> dict:
    return exchange(ws, "session.start", {"source_lang": "vi", "target_lang": "en"})


def test_start_input_and_output_are_connected_without_text_on_wire(tmp_path):
    with TestClient(create_app(tmp_path / "computer.db")) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({
                "v": 1, "type": "session.start", "message_id": "m1",
                "payload": {"source_lang": "vi", "target_lang": "en"},
            })
            started = ws.receive_json()
            assert started["type"] == "session.started"
            session_id = started["session_id"]

            ws.send_json({
                "v": 1, "type": "audio.input", "message_id": "m2",
                "session_id": session_id, "payload": frame_payload(),
            })
            output = ws.receive_json()
            assert output["type"] == "audio.output"
            assert output["payload"]["stream_id"] == "a2b"
            assert output["payload"]["input_seq_start"] == 0
            assert "translation" not in output["payload"]


def test_audio_translation_runs_configured_provider_off_event_loop(tmp_path):
    from computer.server.providers import TranslationResult

    calls = []

    class Provider:
        def translate(self, audio, source, target):
            calls.append((source, target))
            return TranslationResult(b"translated", "internal", "internal")

    with TestClient(create_app(tmp_path / "voice.db", provider_factory=Provider)) as client:
        with client.websocket_connect("/ws") as ws:
            started = start(ws)
            session_id = started["session_id"]
            result = exchange(ws, "audio.input", frame_payload(), session_id)
            assert result["type"] == "audio.output"
            assert result["payload"]["data_b64"] != frame_payload()["data_b64"]
            assert "translation" not in result["payload"]
            assert calls == [("vi", "en")]


def test_provider_failure_returns_safe_error_and_keeps_session(tmp_path):
    from computer.server.providers import ProviderError

    class Provider:
        def translate(self, audio, source, target):
            raise ProviderError("provider failed (HTTP 401)")

    with TestClient(create_app(tmp_path / "voice.db", provider_factory=Provider)) as client:
        with client.websocket_connect("/ws") as ws:
            started = start(ws)
            session_id = started["session_id"]
            error = exchange(ws, "audio.input", frame_payload(), session_id)
            assert error["payload"]["code"] == "provider_unavailable"
            assert "401" not in error["payload"]["detail"]
            assert exchange(ws, "session.cancel", {}, session_id)["type"] == "session.cancelled"


def test_cancel_prevents_later_audio(tmp_path):
    with TestClient(create_app(tmp_path / "computer.db")) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({
                "v": 1, "type": "session.start", "message_id": "m1",
                "payload": {"source_lang": "vi", "target_lang": "en"},
            })
            session_id = ws.receive_json()["session_id"]
            ws.send_json({
                "v": 1, "type": "session.cancel", "message_id": "m2",
                "session_id": session_id, "payload": {},
            })
            assert ws.receive_json()["type"] == "session.cancelled"
            ws.send_json({
                "v": 1, "type": "audio.input", "message_id": "m3",
                "session_id": session_id, "payload": frame_payload(),
            })
            error = ws.receive_json()
            assert error["type"] == "error"
            assert error["payload"]["code"] == "session_not_active"


def test_settings_round_trip_after_restart(tmp_path, monkeypatch):
    database = tmp_path / "settings" / "computer.db"
    monkeypatch.setenv("VOICE_TRANSLATION_DB_PATH", str(database))
    with TestClient(create_app()) as client:
        assert client.get("/settings").json() == {"source_lang": "vi", "target_lang": "en"}
        settings = {"source_lang": "ja", "target_lang": "fr"}
        response = client.put("/settings", json=settings)
        assert response.status_code == 200
        assert response.json() == settings
    with TestClient(create_app()) as client:
        assert client.get("/settings").json() == settings


@pytest.mark.parametrize("changes", [
    {"source_lang": "xx"}, {"target_lang": "vi"}, {"resume_token": "extra"},
])
def test_settings_reject_unsupported_values_without_overwriting(tmp_path, changes):
    with TestClient(create_app(tmp_path / "computer.db")) as client:
        original = {"source_lang": "vi", "target_lang": "en"}
        assert client.put("/settings", json={**original, **changes}).status_code == 422
        assert client.get("/settings").json() == original


def test_failed_settings_write_rolls_back_both_languages(tmp_path):
    database = tmp_path / "computer.db"
    with TestClient(create_app(database)) as client:
        original = {"source_lang": "vi", "target_lang": "en"}
        assert client.put("/settings", json=original).status_code == 200
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("""
                CREATE TRIGGER reject_target BEFORE UPDATE ON operator_config
                WHEN NEW.key = 'target_lang' BEGIN SELECT RAISE(ABORT, 'test failure'); END
            """)
        response = client.put("/settings", json={"source_lang": "fr", "target_lang": "ja"})
        assert response.status_code == 503
        assert client.get("/settings").json() == original
