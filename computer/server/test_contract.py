"""Contract tests for the replacement computer server."""
import base64
import json

import pytest

from computer.server.contract import (
    AudioFormat,
    AudioInput,
    ContractError,
    Envelope,
    SessionStart,
    decode_envelope,
    encode_envelope,
)


def test_session_start_round_trips_without_audio_text():
    envelope = Envelope(
        message_type="session.start",
        session_id=None,
        payload=SessionStart(
            source_lang="vi",
            target_lang="en",
            audio=AudioFormat(16000, 1, "pcm_s16le", 20),
        ).to_payload(),
    )

    decoded = decode_envelope(encode_envelope(envelope))

    assert decoded.version == 1
    assert decoded.message_type == "session.start"
    assert decoded.payload["source_lang"] == "vi"
    assert "transcript" not in decoded.payload


def test_audio_input_rejects_wrong_frame_length():
    payload = {
        "stream_id": "a2b",
        "seq": 0,
        "capture_time_ms": 0,
        "duration_ms": 20,
        "data_b64": base64.b64encode(b"too-short").decode("ascii"),
    }

    with pytest.raises(ContractError, match="frame length"):
        AudioInput.from_payload(payload, AudioFormat(16000, 1, "pcm_s16le", 20))


def test_unknown_envelope_type_is_rejected():
    with pytest.raises(ContractError, match="unknown message type"):
        decode_envelope(json.dumps({"v": 1, "type": "unknown", "message_id": "x", "payload": {}}))
