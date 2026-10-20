"""Synthetic fixtures for the harness tests. This is technical test data only:
not a measurement of any model, GPU, or device. Timestamps are hand-picked ms values.
"""

from __future__ import annotations
import json
import tempfile
from pathlib import Path


def write_jsonl(lines: list) -> str:
    """Write lines (dicts or raw strings) to a temp JSONL file, return path."""
    fd, path = tempfile.mkstemp(suffix=".jsonl", text=True)
    with open(fd, "w") as f:
        for line in lines:
            if isinstance(line, str):
                f.write(line + "\n")
            else:
                f.write(json.dumps(line) + "\n")
    return path


# Four utterances across three sessions: cold/warm states, two directions.
# Schema: session_id, utterance_id, direction, event, timestamp_ms, warm_state (on capture_end only).
CLEAN_EVENTS = [
    # s1/u1 a2b cold: capture=1000 -> audio=1300
    {"session_id": "s1", "utterance_id": "u1", "direction": "a2b", "event": "capture_end", "timestamp_ms": 1000, "warm_state": "cold"},
    {"session_id": "s1", "utterance_id": "u1", "direction": "a2b", "event": "asr_end", "timestamp_ms": 1100},
    {"session_id": "s1", "utterance_id": "u1", "direction": "a2b", "event": "nmt_end", "timestamp_ms": 1200},
    {"session_id": "s1", "utterance_id": "u1", "direction": "a2b", "event": "first_audio", "timestamp_ms": 1300},
    # s1/u2 a2b warm: capture=2000 -> audio=2300
    {"session_id": "s1", "utterance_id": "u2", "direction": "a2b", "event": "capture_end", "timestamp_ms": 2000, "warm_state": "warm"},
    {"session_id": "s1", "utterance_id": "u2", "direction": "a2b", "event": "asr_end", "timestamp_ms": 2110},
    {"session_id": "s1", "utterance_id": "u2", "direction": "a2b", "event": "nmt_end", "timestamp_ms": 2210},
    {"session_id": "s1", "utterance_id": "u2", "direction": "a2b", "event": "first_audio", "timestamp_ms": 2300},
    # s2/u1 b2a cold: capture=5000 -> audio=5400
    {"session_id": "s2", "utterance_id": "u1", "direction": "b2a", "event": "capture_end", "timestamp_ms": 5000, "warm_state": "cold"},
    {"session_id": "s2", "utterance_id": "u1", "direction": "b2a", "event": "asr_end", "timestamp_ms": 5200},
    {"session_id": "s2", "utterance_id": "u1", "direction": "b2a", "event": "nmt_end", "timestamp_ms": 5350},
    {"session_id": "s2", "utterance_id": "u1", "direction": "b2a", "event": "first_audio", "timestamp_ms": 5400},
    # s3/u1 b2a cold: capture=9000 -> audio=9250
    {"session_id": "s3", "utterance_id": "u1", "direction": "b2a", "event": "capture_end", "timestamp_ms": 9000, "warm_state": "cold"},
    {"session_id": "s3", "utterance_id": "u1", "direction": "b2a", "event": "asr_end", "timestamp_ms": 9100},
    {"session_id": "s3", "utterance_id": "u1", "direction": "b2a", "event": "nmt_end", "timestamp_ms": 9180},
    {"session_id": "s3", "utterance_id": "u1", "direction": "b2a", "event": "first_audio", "timestamp_ms": 9250},
]


def clean_jsonl() -> str:
    return write_jsonl(CLEAN_EVENTS)


def write_dir(files: dict[str, list]) -> str:
    d = Path(tempfile.mkdtemp())
    for name, lines in files.items():
        (d / name).write_text("\n".join(
            json.dumps(l) if isinstance(l, dict) else l for l in lines
        ) + "\n")
    return str(d)
