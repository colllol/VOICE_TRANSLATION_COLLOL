"""Tests for FastAPI WebSocket transport."""
import base64
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from protocol.messages import Direction


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


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
                "payload_b64": _b64(b"audio"),
            }
        })
        ack = ws.receive_json()
        assert ack["type"] == "audio_chunk_accepted"
        assert ack["session_id"] == "sess-001"
        assert ack["direction"] == "a2b"
        assert ack["seq"] == 0

        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 1,
                "timestamp_ms": 1200.0,
                "payload_b64": _b64(b"audio2"),
            }
        })
        ack2 = ws.receive_json()
        assert ack2["type"] == "audio_chunk_accepted"
        assert ack2["seq"] == 1


def test_audio_chunk_session_not_found(client):
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "unknown",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 1000.0,
                "payload_b64": _b64(b"audio"),
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
                "payload_b64": _b64(b"audio"),
            }
        })
        ws.receive_json()  # ack seq 1

        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 1200.0,
                "payload_b64": _b64(b"audio2"),
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
                    "payload_b64": _b64(f"audio{i}".encode()),
                }
            })
            ws.receive_json()  # ack

        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 2,
                "timestamp_ms": 1300.0,
                "payload_b64": _b64(b"audio2"),
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
                "payload_b64": _b64(b"audio"),
            }
        })
        ack1 = ws.receive_json()
        assert ack1["type"] == "audio_chunk_accepted"

        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "b2a",
                "seq": 0,
                "timestamp_ms": 1200.0,
                "payload_b64": _b64(b"audio2"),
            }
        })
        ack2 = ws.receive_json()
        assert ack2["type"] == "audio_chunk_accepted"


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


def test_non_object_envelope(client):
    """Envelope must be a JSON object, not array/string/number/null."""
    with client.websocket_connect("/ws/session") as ws:
        ws.send_text('["array"]')
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "envelope must be JSON object" in msg["detail"]

        ws.send_text('"string"')
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "envelope must be JSON object" in msg["detail"]

        ws.send_text('42')
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "envelope must be JSON object" in msg["detail"]

        ws.send_text('null')
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "envelope must be JSON object" in msg["detail"]


def test_non_object_payload(client):
    """Payload must be a JSON object, not array/string/number/null."""
    with client.websocket_connect("/ws/session") as ws:
        ws.send_json({"type": "session_start", "payload": ["array"]})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "payload must be JSON object" in msg["detail"]

        ws.send_json({"type": "session_start", "payload": "string"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "payload must be JSON object" in msg["detail"]

        ws.send_json({"type": "session_start", "payload": 42})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "payload must be JSON object" in msg["detail"]


def test_audio_chunk_missing_payload_b64(client):
    """Missing payload_b64 field returns invalid_message."""
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
        ws.receive_json()

        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 1100.0,
            }
        })
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "invalid_message"
        assert "payload_b64 must be a string" in msg["detail"]


def test_audio_chunk_invalid_base64(client):
    """Invalid base64 returns invalid_message."""
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
        ws.receive_json()

        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 1100.0,
                "payload_b64": "not!!!valid===base64",
            }
        })
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "invalid_message"
        assert "invalid base64" in msg["detail"]


def test_audio_chunk_strict_base64(client):
    """Strict RFC4648 base64 validation."""
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
        ws.receive_json()

        # Valid base64
        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 1100.0,
                "payload_b64": _b64(b"\x00\x01\x02\x03\xff\xfe"),
            }
        })
        ack = ws.receive_json()
        assert ack["type"] == "audio_chunk_accepted"


def test_disconnect_cleanup_owned_sessions(client):
    """Disconnect cancels only sessions started by this WebSocket."""
    with client.websocket_connect("/ws/session") as ws1:
        ws1.send_json({
            "type": "session_start",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 1000.0,
                "source_lang": "vi",
                "target_lang": "en",
            }
        })
        ws1.receive_json()

        # Send another message to verify session is active before checking service
        ws1.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 1100.0,
                "payload_b64": _b64(b"audio"),
            }
        })
        ack = ws1.receive_json()
        assert ack["type"] == "audio_chunk_accepted"

    # After disconnect, check via a new connection that session cannot be used
    with client.websocket_connect("/ws/session") as ws2:
        ws2.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 1,
                "timestamp_ms": 1200.0,
                "payload_b64": _b64(b"audio2"),
            }
        })
        msg = ws2.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "session_not_active"


def test_disconnect_isolation(client):
    """Disconnect only cancels sessions owned by the disconnecting WebSocket."""
    # Create two concurrent connections with distinct sessions
    ws1 = client.websocket_connect("/ws/session").__enter__()
    ws1.send_json({
        "type": "session_start",
        "payload": {
            "session_id": "sess-001",
            "timestamp_ms": 1000.0,
            "source_lang": "vi",
            "target_lang": "en",
        }
    })
    ws1.receive_json()

    ws2 = client.websocket_connect("/ws/session").__enter__()
    ws2.send_json({
        "type": "session_start",
        "payload": {
            "session_id": "sess-002",
            "timestamp_ms": 2000.0,
            "source_lang": "en",
            "target_lang": "vi",
        }
    })
    ws2.receive_json()

    # Both sessions should work
    ws1.send_json({
        "type": "audio_chunk",
        "payload": {
            "session_id": "sess-001",
            "direction": "a2b",
            "seq": 0,
            "timestamp_ms": 1100.0,
            "payload_b64": _b64(b"a1"),
        }
    })
    ack1 = ws1.receive_json()
    assert ack1["type"] == "audio_chunk_accepted"

    ws2.send_json({
        "type": "audio_chunk",
        "payload": {
            "session_id": "sess-002",
            "direction": "a2b",
            "seq": 0,
            "timestamp_ms": 2100.0,
            "payload_b64": _b64(b"a2"),
        }
    })
    ack2 = ws2.receive_json()
    assert ack2["type"] == "audio_chunk_accepted"

    # Disconnect ws2
    ws2.__exit__(None, None, None)

    # sess-001 should still work via ws1
    ws1.send_json({
        "type": "audio_chunk",
        "payload": {
            "session_id": "sess-001",
            "direction": "a2b",
            "seq": 1,
            "timestamp_ms": 1200.0,
            "payload_b64": _b64(b"a3"),
        }
    })
    ack3 = ws1.receive_json()
    assert ack3["type"] == "audio_chunk_accepted"

    # sess-002 should be dead (ws2 disconnected)
    ws1.send_json({
        "type": "audio_chunk",
        "payload": {
            "session_id": "sess-002",
            "direction": "a2b",
            "seq": 1,
            "timestamp_ms": 2200.0,
            "payload_b64": _b64(b"dead"),
        }
    })
    err = ws1.receive_json()
    assert err["type"] == "error"
    assert err["code"] == "session_not_active"

    ws1.__exit__(None, None, None)


def test_disconnect_no_double_cancel(client):
    """Disconnect does not cancel already-ended sessions."""
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
        ws.receive_json()

        # Explicitly end session
        ws.send_json({
            "type": "session_end",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 2000.0,
                "reason": "completed",
            }
        })
        end_ack = ws.receive_json()
        assert end_ack["type"] == "session_ended"

    # Verify session was ended, not active anymore
    with client.websocket_connect("/ws/session") as ws2:
        ws2.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 3000.0,
                "payload_b64": _b64(b"audio"),
            }
        })
        msg = ws2.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "session_not_active"


def test_ack_no_hidden_messages(client):
    """After receiving ACK, no hidden messages are pending."""
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
        start_ack = ws.receive_json()
        assert start_ack["type"] == "session_started"

        ws.send_json({
            "type": "audio_chunk",
            "payload": {
                "session_id": "sess-001",
                "direction": "a2b",
                "seq": 0,
                "timestamp_ms": 1100.0,
                "payload_b64": _b64(b"audio"),
            }
        })
        chunk_ack = ws.receive_json()
        assert chunk_ack["type"] == "audio_chunk_accepted"

        # Send another message immediately - should work
        ws.send_json({
            "type": "session_end",
            "payload": {
                "session_id": "sess-001",
                "timestamp_ms": 2000.0,
                "reason": "completed",
            }
        })
        end_ack = ws.receive_json()
        assert end_ack["type"] == "session_ended"
