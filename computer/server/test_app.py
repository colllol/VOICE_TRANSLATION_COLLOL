"""Replacement server transport tests."""
import base64

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


def test_start_input_and_output_are_connected_without_text_on_wire():
    with TestClient(create_app()) as client:
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
            assert "transcript" not in output["payload"]


def test_cancel_prevents_later_audio():
    with TestClient(create_app()) as client:
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
