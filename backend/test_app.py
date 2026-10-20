"""Tests for FastAPI WebSocket transport."""
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from protocol.messages import Direction


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "voice-translation-backend"
    assert data["status"] == "ok"


def test_session_start_success(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "session_start",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 1000.0,
                "source_lang": "vi",
                "target_lang": "en",
            }
        })
        msg = ws.receive_json()
        assert msg["type"] == "session_started"
        assert msg["session_id"] == "sess-001"


def test_session_start_duplicate(client):
    with client.websocket_connect("/ws/session") as ws:
        payload = {
            "session_id": "sess-001",
            "timestamp_ms": 1000.0,
            "source_lang": "vi",
            "target_lang": "en",
        }
        ws.send_json({"type": "session_start", "payload": payload})
        ws.receive_json()  # ack

        ws.send_json({"type": "session_start", "payload": payload})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "internal_error"
        assert "already active" in msg["detail"]


def test_session_start_invalid_payload(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "session_start",
            "payload": {
                "session_id": "",  # invalid
                "timestamp_ms": 1000.0,
                "source_lang": "vi",
                "target_lang": "en",
            }
        })
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "invalid_message"


def test_audio_chunk_success(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "session_start",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 1000.0,
                "source_lang": "vi",
                "target_lang": "en",
            }
        })
        ws.receive_json()  # ack

        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 1100.0,
                "payload": "YXVkaW8=",  # base64-like, TestClient handles bytes
            }
        })
        # No error = success (service doesn't send ack for chunks)
        # Check we can send another
        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 1,
                "timestamp_ms": 1200.0,
                "payload": "YXVkaW8y",
            }
        })


def test_audio_chunk_session_not_found(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "unknown",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 1000.0,
                "payload": "YXVkaW8=",
            }
        })
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "session_not_active"


def test_audio_chunk_stale_sequence(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "session_start",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 1000.0,
                "source_lang": "vi",
                "target_lang": "en",
            }
        })
        ws.receive_json()  # ack

        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 1,
                "timestamp_ms": 1100.0,
                "payload": "YXVkaW8=",
            }
        })
        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 1200.0,
                "payload": "YXVkaW8y",
            }
        })
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "stale_sequence"


def test_audio_chunk_backpressure(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "session_start",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 1000.0,
                "source_lang": "vi",
                "target_lang": "en",
                "max_queue_size": 2,
            }
        })
        ws.receive_json()  # ack

        for i in range(2):
            ws.send_json({
                "type": "audio_chunk",
                "payload": {
                    "session_id": "sess-001",
                    "direction": "a2b",
                    "seq": i,
                    "timestamp_ms": 1100.0 + i * 100,
                    "payload": f"audio{i}".encode().hex(),
                }
            })

        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 2,
                "timestamp_ms": 1300.0,
                "payload": "YXVkaW8y",
            }
        })
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "backpressure_exceeded"


def test_session_end_success(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "session_start",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 1000.0,
                "source_lang": "vi",
                "target_lang": "en",
            }
        })
        ws.receive_json()  # ack

        ws.send_json({
            "type": "session_end",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 2000.0,
                "reason": "completed",
            }
        })
        msg = ws.receive_json()
        assert msg["type"] == "session_ended"
        assert msg["session_id"] == "sess-001"


def test_session_end_not_found(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "session_end",
            "payload": {
                "session_id": "unknown",
                "timestamp_ms": 1000.0,
                "reason": "completed",
            }
        })
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "session_not_active"


def test_cancel_session_success(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "session_start",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 1000.0,
                "source_lang": "vi",
                "target_lang": "en",
            }
        })
        ws.receive_json()  # ack

        ws.send_json({
            "type": "cancel_session",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 1500.0,
            }
        })
        msg = ws.receive_json()
        assert msg["type"] == "session_cancelled"
        assert msg["session_id"] == "sess-001"


def test_resume_session_success(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "session_start",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 1000.0,
                "source_lang": "vi",
                "target_lang": "en",
            }
        })
        ws.receive_json()  # ack

        ws.send_json({
            "type": "resume_session",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 1500.0,
                "last_seq_a2b": 10,
                "last_seq_b2a": 5,
            }
        })
        msg = ws.receive_json()
        assert msg["type"] == "session_resumed"
        assert msg["session_id"] == "sess-001"


def test_bidirectional_independence(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "session_start",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 1000.0,
                "source_lang": "vi",
                "target_lang": "en",
            }
        })
        ws.receive_json()  # ack

        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 1100.0,
                "payload": "YXVkaW8=",
            }
        })
        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "b2a",
                "seq": 0,
                "timestamp_ms": 1200.0,
                "payload": "YXVkaW8y",
            }
        })
        # Both succeed, no errors


def test_malformed_json(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_text("not json")
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "malformed JSON" in msg["detail"]


def test_missing_type_field(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({"payload": {"session_id": "sess-001"}})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "missing type field" in msg["detail"]


def test_unknown_message_type(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({"type": "unknown_type", "payload": {}})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "unknown type" in msg["detail"]


def test_missing_payload_field(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({"type": "session_start"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "missing payload field" in msg["detail"]
