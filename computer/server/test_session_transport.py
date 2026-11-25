"""Session lifecycle through the computer WebSocket transport."""
import time

from fastapi.testclient import TestClient

from computer.server.app import create_app
from computer.server.providers import FakeTranslationProvider
from computer.server.storage import SQLiteStore
from computer.server.test_app import frame_payload


def exchange(ws, command, payload, session_id=None):
    message = {"v": 1, "type": command, "message_id": command, "payload": payload}
    if session_id is not None:
        message["session_id"] = session_id
    ws.send_json(message)
    return ws.receive_json()


def start(ws):
    return exchange(ws, "session.start", {"source_lang": "vi", "target_lang": "en"})


def state_for(store, session_id):
    return {row["session_id"]: row["state"] for row in store.list_sessions()}[session_id]


def wait_for_state(store, session_id, expected):
    deadline = time.monotonic() + 2
    while state_for(store, session_id) != expected and time.monotonic() < deadline:
        time.sleep(0.01)
    assert state_for(store, session_id) == expected


def test_disconnect_resume_keeps_sequence_and_persists_state(tmp_path):
    database = tmp_path / "computer.db"
    store = SQLiteStore(database)
    with TestClient(create_app(database)) as client:
        with client.websocket_connect("/ws") as ws:
            started = start(ws)
            session_id = started["session_id"]
            token = started["payload"]["resume_token"]
            assert exchange(ws, "audio.input", frame_payload(), session_id)["type"] == "audio.output"
            with client.websocket_connect("/ws") as other:
                assert exchange(other, "session.resume", {"resume_token": token}, session_id)["type"] == "error"
        wait_for_state(store, session_id, "disconnected_grace")
        with client.websocket_connect("/ws") as ws:
            denied = exchange(ws, "session.resume", {"resume_token": "incorrect"}, session_id)
            assert denied["payload"]["code"] == "resume_rejected"
            resumed = exchange(ws, "session.resume", {"resume_token": token}, session_id)
            assert resumed["type"] == "session.resumed"
            assert state_for(store, session_id) == "active"
            output = exchange(ws, "audio.input", frame_payload(1), session_id)
            assert output["payload"]["output_seq"] == 1
            assert exchange(ws, "session.cancel", {}, session_id)["type"] == "session.cancelled"
        assert state_for(store, session_id) == "cancelled"
        assert token.encode() not in database.read_bytes()


def test_disconnected_session_expires_without_client_activity(tmp_path):
    database = tmp_path / "computer.db"
    store = SQLiteStore(database)
    with TestClient(create_app(database, grace_seconds=0.05)) as client:
        with client.websocket_connect("/ws") as ws:
            started = start(ws)
        wait_for_state(store, started["session_id"], "cancelled")
        response_payload = {"resume_token": started["payload"]["resume_token"]}
        with client.websocket_connect("/ws") as ws:
            response = exchange(ws, "session.resume", response_payload, started["session_id"])
            assert response["payload"]["code"] == "resume_rejected"


def test_bad_messages_do_not_drop_session(tmp_path):
    with TestClient(create_app(tmp_path / "computer.db")) as client:
        with client.websocket_connect("/ws") as ws:
            session_id = start(ws)["session_id"]
            for bad in ("{", "[]", '{"v":true}', " " * 4097):
                ws.send_text(bad)
                assert ws.receive_json()["type"] == "error"
            ws.send_bytes(b"unsupported")
            assert ws.receive_json()["type"] == "error"
            assert start(ws)["payload"]["code"] == "session_already_active"
            bad_frame = {**frame_payload(), "seq": True}
            error = exchange(ws, "audio.input", bad_frame, session_id)
            assert error["type"] == "error"
            assert error["message_id"] == "audio.input"
            assert exchange(ws, "audio.input", frame_payload(), session_id)["type"] == "audio.output"


def test_reverse_audio_swaps_translation_languages(tmp_path, monkeypatch):
    original_translate = FakeTranslationProvider.translate
    languages = []

    def record_languages(self, audio, source, target):
        languages.append((source, target))
        return original_translate(self, audio, source, target)

    monkeypatch.setattr(FakeTranslationProvider, "translate", record_languages)
    with TestClient(create_app(tmp_path / "computer.db")) as client:
        with client.websocket_connect("/ws") as ws:
            session_id = start(ws)["session_id"]
            for stream in ("a2b", "b2a"):
                response = exchange(ws, "audio.input", {**frame_payload(), "stream_id": stream}, session_id)
                assert response["type"] == "audio.output"
                assert response["payload"]["output_seq"] == 0
    assert languages == [("vi", "en"), ("en", "vi")]


def test_restart_reconciles_interrupted_session_metadata(tmp_path):
    database = tmp_path / "computer.db"
    store = SQLiteStore(database)
    store.record_session("interrupted", "vi", "en", "active")
    with TestClient(create_app(database)):
        assert state_for(store, "interrupted") == "cancelled"
