"""Local Windows PCM bridge. VTB1 + big-endian uint32 length + PCM16 payload."""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import struct
from dataclasses import dataclass

MAGIC = b"VTB1"
MAX_FRAME = 64 * 1024
QUEUE_FRAMES = 100


def encode_frame(payload: bytes) -> bytes:
    if not isinstance(payload, bytes) or len(payload) > MAX_FRAME:
        raise ValueError("invalid PCM frame")
    return MAGIC + struct.pack(">I", len(payload)) + payload


async def read_frame(reader: asyncio.StreamReader) -> bytes | None:
    try:
        header = await reader.readexactly(8)
    except asyncio.IncompleteReadError:
        return None
    if header[:4] != MAGIC:
        raise ValueError("invalid bridge magic")
    size = struct.unpack(">I", header[4:])[0]
    if size > MAX_FRAME:
        raise ValueError("bridge frame too large")
    try:
        return await reader.readexactly(size)
    except asyncio.IncompleteReadError as exc:
        raise ValueError("truncated bridge frame") from exc


@dataclass
class BridgeState:
    mode: str = "stopped"
    generation: int = 0

    def set_mode(self, mode, generation=None):
        if mode not in ("active", "stopped"):
            raise ValueError("invalid mode")
        generation = self.generation + 1 if generation is None else generation
        if type(generation) is not int or generation <= self.generation:
            raise ValueError("generation must increase")
        self.mode, self.generation = mode, generation


class LaneProcessor:
    def __init__(self, lane, state, translate, *, synthetic=False):
        if lane not in ("a2b", "b2a"):
            raise ValueError("unknown lane")
        self.lane, self.state, self.translate = lane, state, translate
        self.synthetic = synthetic
        self.queue = asyncio.Queue(maxsize=QUEUE_FRAMES)
        self.worker = None
        self.output = bytearray()
        self.ready = asyncio.Queue(maxsize=QUEUE_FRAMES)

    def synthetic_tone(self, payload):
        hz = 440 if self.lane == "a2b" else 660
        return b"".join(struct.pack("<h", round(5000 * math.sin(2 * math.pi * hz * i / 16000))) for i in range(len(payload) // 2))

    async def process(self, payload: bytes) -> bytes:
        if self.state.mode == "stopped":
            self.output.clear()
            return payload
        generation = self.state.generation
        if self.synthetic:
            return self._fit_output(self.synthetic_tone(payload), len(payload))
        if len(self.output) >= len(payload):
            return self._fit_output(b"", len(payload))
        if not self.ready.empty():
            ready_generation, translated = self.ready.get_nowait()
            if ready_generation == generation:
                return self._fit_output(translated, len(payload))
        if self.worker is None or self.worker.done():
            self.worker = asyncio.create_task(self._run())
        try:
            self.queue.put_nowait((generation, payload))
        except asyncio.QueueFull:
            return b"\0" * len(payload)
        return b"\0" * len(payload)

    def _fit_output(self, translated: bytes, requested: int) -> bytes:
        self.output.extend(translated)
        result = bytes(self.output[:requested])
        del self.output[:len(result)]
        return result.ljust(requested, b"\0")

    async def _run(self):
        while True:
            generation, pcm = await self.queue.get()
            group = [pcm]
            await asyncio.sleep(0.06)
            while not self.queue.empty() and len(group) < 50:
                item_generation, item_pcm = self.queue.get_nowait()
                if item_generation == generation:
                    group.append(item_pcm)
            try:
                result = await self.translate(b"".join(group), self.lane)
                if not isinstance(result, bytes) or not result: raise ValueError("invalid backend audio")
                if self.state.mode == "active" and generation == self.state.generation:
                    if self.ready.full():
                        self.ready.get_nowait()
                    self.ready.put_nowait((generation, result))
            except Exception:
                continue


class BackendLane:
    def __init__(self, url, lane):
        self.url, self.lane, self.ws, self.seq = url, lane, None, 0
        self.session_id = None
        self.request_id = 0

    async def connect(self):
        import websockets
        self.ws = await websockets.connect(self.url)
        reply = await self._send("session.start", {"source_lang": "vi", "target_lang": "en"})
        if reply.get("type") != "session.started" or not reply.get("session_id"):
            raise RuntimeError("backend session rejected")
        self.session_id = reply["session_id"]

    async def _send(self, kind, payload):
        request = self.request_id
        self.request_id += 1
        message_id = f"bridge-{self.lane}-{request}"
        message = {"v": 1, "type": kind, "message_id": message_id, "payload": payload}
        if self.session_id is not None: message["session_id"] = self.session_id
        await self.ws.send(json.dumps(message))
        reply = json.loads(await self.ws.recv())
        if (reply.get("message_id") != message_id or reply.get("type") == "error"
                or (self.session_id is not None and reply.get("session_id") != self.session_id)):
            raise RuntimeError("backend response validation failed")
        return reply

    async def translate(self, pcm, lane):
        if self.ws is None:
            await self.connect()
        frame_bytes = 640
        for offset in range(0, len(pcm), frame_bytes):
            frame = pcm[offset:offset + frame_bytes]
            if len(frame) != frame_bytes:
                frame = frame.ljust(frame_bytes, b"\0")
            chunk = {"stream_id": lane, "seq": self.seq,
                     "data_b64": base64.b64encode(frame).decode("ascii")}
            self.seq += 1
            ack = await self._send("utterance.chunk", chunk)
            if (ack.get("type") != "utterance.ack" or ack.get("session_id") != self.session_id
                    or ack.get("payload", {}).get("stream_id") != lane
                    or ack.get("payload", {}).get("seq") != chunk["seq"]):
                raise RuntimeError("backend rejected PCM")
        result = await self._send("utterance.finish", {"stream_id": lane})
        if result.get("type") != "utterance.output" or result.get("session_id") != self.session_id:
            raise RuntimeError("backend returned no PCM")
        audio = base64.b64decode(result["payload"]["data_b64"], validate=True)
        if len(audio) > 60 * 32000:
            raise RuntimeError("backend output exceeds negotiated limit")
        return audio


async def serve_lane(host, port, processor):
    async def client(reader, writer):
        try:
            while (frame := await read_frame(reader)) is not None:
                writer.write(encode_frame(await processor.process(frame)))
                await writer.drain()
        except (ConnectionError, ValueError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
    return await asyncio.start_server(client, host, port)


async def serve_control(host, port, state, processors):
    async def client(reader, writer):
        try:
            msg = json.loads(await reader.readline())
            if msg.get("type") != "mode":
                raise ValueError
            state.set_mode(msg.get("mode"), msg.get("generation"))
            for processor in processors:
                processor.output.clear()
                while not processor.ready.empty():
                    processor.ready.get_nowait()
            writer.write(json.dumps({"ok": True, "mode": state.mode, "generation": state.generation}).encode() + b"\n")
        except (ValueError, json.JSONDecodeError):
            writer.write(b'{"ok":false}\n')
        await writer.drain()
        writer.close()
        await writer.wait_closed()
    return await asyncio.start_server(client, host, port)


async def run(args):
    state = BridgeState()
    processors = []
    for lane in ("a2b", "b2a"):
        backend = BackendLane(args.backend, lane) if args.backend else None
        processors.append(LaneProcessor(lane, state, backend.translate if backend else None, synthetic=backend is None))
    servers = [await serve_lane(args.host, args.a2b_port, processors[0]),
               await serve_lane(args.host, args.b2a_port, processors[1]),
               await serve_control(args.host, args.control_port, state, processors)]
    await asyncio.gather(*(s.serve_forever() for s in servers))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", help="local backend WebSocket URL; omit for non-identity synthetic tones")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--a2b-port", type=int, default=19091)
    parser.add_argument("--b2a-port", type=int, default=19092)
    parser.add_argument("--control-port", type=int, default=19090)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()