"""Run synthetic native Baresip calls through the 8 kHz VT08 PCM fixture."""

import argparse
import asyncio
import math
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import threading
import time
import wave

async def read_frame(reader):
    try:
        header = await reader.readexactly(8)
        if header[:4] != b"VT08": raise ValueError("expected 8 kHz VT08")
        size = struct.unpack(">I", header[4:])[0]
        if size > 8192 or size % 2: raise ValueError("invalid PCM size")
        return await reader.readexactly(size)
    except asyncio.IncompleteReadError:
        return None

def encode_frame(payload):
    return b"VT08" + struct.pack(">I", len(payload)) + payload


class FixtureProcessor:
    def __init__(self, lane, disconnected=False):
        self.lane, self.disconnected, self.sample_index = lane, disconnected, 0

    async def process(self, payload):
        if self.disconnected:
            return bytes(len(payload))
        hz = 440 if self.lane == "a2b" else 660
        samples = []
        for _ in range(len(payload) // 2):
            samples.append(round(5000 * math.sin(2 * math.pi * hz * self.sample_index / 8000)))
            self.sample_index += 1
        return struct.pack(f"<{len(samples)}h", *samples)


async def serve_lane(host, port, processor):
    async def client(reader, writer):
        try:
            while (payload := await read_frame(reader)) is not None:
                if processor.disconnected:
                    break
                writer.write(encode_frame(await processor.process(payload)))
                await writer.drain()
        except (ConnectionError, ValueError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
    return await asyncio.start_server(client, host, port)


def launch_bridge(ports, disconnected):
    ready, holder = threading.Event(), {}
    def worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        processors = [FixtureProcessor("a2b", disconnected), FixtureProcessor("b2a", disconnected)]
        servers = loop.run_until_complete(asyncio.gather(
            serve_lane("127.0.0.1", ports[0], processors[0]),
            serve_lane("127.0.0.1", ports[1], processors[1])))
        holder.update(loop=loop, servers=servers)
        ready.set()
        loop.run_forever()
        for server in servers:
            server.close()
        loop.run_until_complete(asyncio.gather(*(server.wait_closed() for server in servers)))
        loop.close()
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    if not ready.wait(3):
        raise RuntimeError("bridge listeners did not start")
    return holder, thread


def dominant_amplitude(samples, hz):
    phase = math.tau * hz / 8000
    real = sum(value * math.cos(phase * index) for index, value in enumerate(samples))
    imag = sum(value * math.sin(phase * index) for index, value in enumerate(samples))
    return 2 * math.hypot(real, imag) / len(samples)


def verify_media(peer, samples, mode):
    if isinstance(mode, bool):
        if mode:
            expected = -3000 if peer == "a" else 3000
            if len(samples) != 8000:
                raise RuntimeError(f"Peer {peer}: expected 8000 samples, {len(samples)} samples received")
            off_target = sum(abs(value - expected) > 100 for value in samples)
            if off_target:
                raise RuntimeError(f"Peer {peer}: {off_target} off-target samples; expected {expected}")
            return
        mode = "baseline"
    if len(samples) != 8000:
        raise RuntimeError(f"Peer {peer}: expected 8000 samples, {len(samples)} samples received")
    if mode == "disconnect":
        if peer == "b" and max(abs(value) for value in samples) > 2:
            raise RuntimeError(f"Peer {peer}: disconnected bridge leaked PCM")
        if peer == "a" and max(abs(value) for value in samples) > 2:
            raise RuntimeError(f"Peer {peer}: disconnected bridge leaked PCM")
        return
    hz = (440 if peer == "b" else 660) if mode == "replacement" else (700 if peer == "a" else 400)
    if dominant_amplitude(samples, hz) < (3000 if mode == "replacement" else 4000):
        raise RuntimeError(f"Peer {peer}: expected {hz} Hz; amplitude={dominant_amplitude(samples, hz):.0f}")


def run(exe: Path, scratch: Path, *, mode="replacement", load_filter=True):
    directory = tempfile.mkdtemp(prefix=f"vt005-{mode}-", dir=scratch)
    print(f"Probe artifacts: {directory}", flush=True)
    root = Path(directory)
    ports = [19091, 19092]
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError as exc:
                raise RuntimeError(f"VT005 bridge port {port} unavailable: {exc}") from exc
    for _ in range(2):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            ports.append(sock.getsockname()[1])
    bridge, bridge_thread = launch_bridge(ports[:2], mode == "disconnect")
    for name, port, frequency in (("a", ports[2], 400), ("b", ports[3], 700)):
        folder = root / name
        folder.mkdir()
        modules = "module g711.dll\nmodule ausine.dll\nmodule aufile.dll\n"
        if name == "a" and load_filter and mode != "baseline":
            modules += "module vt005_probe.dll\n"
        (folder / "config").write_text(
            f"sip_listen 127.0.0.1:{port}\nsip_transports udp\n"
            f"audio_source ausine,{frequency}\n"
            f"audio_player aufile,{(folder / 'received.wav').as_posix()}\n"
            f"{modules}module_app account.dll\nmodule_app menu.dll\n", encoding="ascii")
        (folder / "accounts").write_text(
            f"<sip:{name}@127.0.0.1:{port}>;regint=0;answermode=auto;audio_codecs=PCMU/8000/1\n",
            encoding="ascii")
    logs = {name: (root / f"{name}.log").open("w") for name in ("a", "b")}
    def start(name, duration, *args):
        return subprocess.Popen([str(exe), "-4", "-c", "-n", "127.0.0.1", "-f", str(root / name),
                                 "-t", str(duration), *args], cwd=root / name,
                                stdin=subprocess.DEVNULL, stdout=logs[name], stderr=subprocess.STDOUT)
    try:
        with start("b", 10) as b_proc:
            try:
                deadline = time.monotonic() + 4
                while "baresip is ready" not in (root / "b.log").read_text(errors="replace"):
                    if b_proc.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError((root / "b.log").read_text(errors="replace"))
                    time.sleep(0.05)
                with start("a", 5, "-e", f"/dial sip:b@127.0.0.1:{ports[3]}") as a_proc:
                    try:
                        code_a = a_proc.wait(timeout=8)
                    finally:
                        if a_proc.poll() is None:
                            a_proc.kill()
                code_b = b_proc.wait(timeout=12)
            finally:
                if b_proc.poll() is None:
                    b_proc.kill()
    finally:
        for log in logs.values():
            log.close()
        bridge["loop"].call_soon_threadsafe(bridge["loop"].stop)
        bridge_thread.join(timeout=3)
    for peer, code in (("a", code_a), ("b", code_b)):
        log = (root / f"{peer}.log").read_text(errors="replace")
        if code != 0 or "Call established" not in log:
            raise RuntimeError(f"Peer {peer}, exit {code}:\\n{log}")
        for role in ("encoder", "decoder"):
            if f"Set audio {role}: PCMU 8000Hz 1ch" not in log:
                raise RuntimeError(f"Peer {peer}: expected PCMU {role}:\\n{log}")
        with wave.open(str(root / peer / "received.wav"), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 8000):
                raise RuntimeError(f"Peer {peer}: expected mono 16-bit 8 kHz WAV")
            if wav.getnframes() < 16000:
                raise RuntimeError(f"Peer {peer}: WAV too short")
            wav.setpos(8000)
            samples = [value for (value,) in struct.iter_unpack("<h", wav.readframes(8000))]
        verify_media(peer, samples, mode)
        print(f"{peer}: mode={mode}, PCMU, samples={len(samples)}, range=[{min(samples)}, {max(samples)}]")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path)
    parser.add_argument("scratch", type=Path)
    parser.add_argument("--mode", choices=("baseline", "replacement", "disconnect"), default="replacement")
    parser.add_argument("--a2b-port", type=int, default=19091)
    parser.add_argument("--b2a-port", type=int, default=19092)
    parser.add_argument("--omit-filter", action="store_true")
    args = parser.parse_args()
    run(args.exe.resolve(strict=True), args.scratch.resolve(strict=True),
        mode=args.mode, load_filter=not args.omit_filter)
