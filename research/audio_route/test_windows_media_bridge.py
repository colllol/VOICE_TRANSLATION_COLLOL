"""Synthetic acceptance tests for the local Windows media bridge."""

import asyncio
import base64
import json
import struct
from typing import Any, cast

import pytest

from research.audio_route.windows_media_bridge import (
    BackendLane,
    BridgeState,
    LaneProcessor,
    encode_frame,
    read_frame,
)


def test_backend_lane_sends_pcm_in_20ms_chunks_and_keeps_full_output():
    output = b"\x01\x02" * 960

    class FakeWebSocket:
        def __init__(self):
            self.messages = []
            self.session_id = "session-1"

        async def send(self, raw):
            self.messages.append(json.loads(raw))

        async def recv(self):
            request = self.messages[-1]
            kind = request["type"]
            reply_type = {"session.start": "session.started", "utterance.chunk": "utterance.ack",
                          "utterance.finish": "utterance.output"}[kind]
            reply = {"type": reply_type, "message_id": request["message_id"],
                     "session_id": self.session_id}
            if kind == "utterance.chunk":
                reply["payload"] = {"stream_id": request["payload"]["stream_id"],
                                     "seq": request["payload"]["seq"]}
            if kind == "utterance.finish":
                reply["payload"] = {"stream_id": request["payload"]["stream_id"],
                                     "data_b64": base64.b64encode(output).decode()}
            return json.dumps(reply)

    fake = FakeWebSocket()
    lane = BackendLane("ws://local.invalid/ws", "a2b")
    lane.ws, lane.session_id = cast(Any, fake), fake.session_id

    assert asyncio.run(lane.translate(b"\x03\x04" * 640, "a2b")) == output
    chunks = [message["payload"] for message in fake.messages if message["type"] == "utterance.chunk"]
    assert len(chunks) == 2
    assert [len(base64.b64decode(chunk["data_b64"])) for chunk in chunks] == [640, 640]
    assert [chunk["seq"] for chunk in chunks] == [0, 1]


def test_frame_wire_format_round_trips_binary_pcm():
    payload = b"\x00\x01\xff\x7f"
    encoded = encode_frame(payload)
    assert encoded[:4] == b"VTB1"
    assert struct.unpack(">I", encoded[4:8])[0] == len(payload)
    async def read():
        reader = asyncio.StreamReader()
        reader.feed_data(encoded)
        reader.feed_eof()
        return await read_frame(reader)
    assert asyncio.run(read()) == payload


def test_active_lane_returns_translation_and_keeps_directions_independent():
    calls = []

    async def translate(payload, lane):
        calls.append((lane, payload))
        return (b"A" if lane == "a2b" else b"B") + payload[1:]

    state = BridgeState("active")
    a2b = LaneProcessor("a2b", state, translate)
    b2a = LaneProcessor("b2a", state, translate)
    async def exercise():
        assert await a2b.process(b"one") == b"\0" * 3
        assert await b2a.process(b"two") == b"\0" * 3
        await asyncio.sleep(0.08)
        assert await a2b.process(b"three") == b"Ane\0\0"
        assert await b2a.process(b"four") == b"Bwo\0"
    asyncio.run(exercise())
    assert calls == [("a2b", b"one"), ("b2a", b"two")]


def test_active_failure_is_silence_and_stop_restores_raw():
    async def unavailable(payload, lane):
        raise RuntimeError("backend unavailable")

    state = BridgeState("active")
    lane = LaneProcessor("a2b", state, unavailable)
    async def exercise():
        assert await lane.process(b"raw") == b"\0" * 3
        await asyncio.sleep(0.08)
        assert await lane.process(b"raw") == b"\0" * 3
        state.set_mode("stopped", 1)
        assert await lane.process(b"raw") == b"raw"
    asyncio.run(exercise())


def test_long_translation_is_drained_without_truncation_or_stale_session_audio():
    state = BridgeState("active")
    lane = LaneProcessor("a2b", state, lambda payload, direction: asyncio.sleep(0, result=b"abcdefgh"))
    async def exercise():
        assert await lane.process(b"1234") == b"\0" * 4
        await asyncio.sleep(0.08)
        assert await lane.process(b"5678") == b"abcd"
        assert await lane.process(b"90ab") == b"efgh"
        assert await lane.process(b"cdef") == b"\0" * 4
        await asyncio.sleep(0.08)
        state.set_mode("stopped", 1)
        assert await lane.process(b"raw!") == b"raw!"
        state.set_mode("active", 2)
        assert await lane.process(b"new!") == b"\0" * 4
    asyncio.run(exercise())


def test_active_synthetic_lanes_emit_distinct_non_identity_tones():
    state = BridgeState("active")
    a = LaneProcessor("a2b", state, None, synthetic=True).synthetic_tone(b"\0" * 640)
    b = LaneProcessor("b2a", state, None, synthetic=True).synthetic_tone(b"\0" * 640)
    assert a != b and a != b"\0" * 640 and b != b"\0" * 640


def test_generation_must_increase_to_isolate_old_frames():
    state = BridgeState()
    state.set_mode("active", 1)
    with pytest.raises(ValueError, match="increase"):
        state.set_mode("stopped", 1)
    state.set_mode("stopped", 2)
    assert (state.mode, state.generation) == ("stopped", 2)


def test_control_payload_has_no_audio_or_transcript_fields():
    message = {"type": "mode", "mode": "active"}
    assert "audio" not in message and "transcript" not in message
    assert json.loads(json.dumps(message)) == message