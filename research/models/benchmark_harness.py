"""Deterministic latency summaries for JSONL instrumentation events; no inference is run here."""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Sample:
    session_id: str
    utterance_id: str
    direction: str
    warm_state: str
    capture_to_asr_ms: float
    capture_to_nmt_ms: float
    capture_to_first_audio_ms: float


class Schema:
    EVENTS = {"capture_end", "asr_end", "nmt_end", "first_audio"}
    DIRECTIONS = {"a2b", "b2a"}
    WARM_STATES = {"cold", "warm"}
    REQUIRED = {"session_id", "utterance_id", "direction", "event", "timestamp_ms"}

    @classmethod
    def validate(cls, obj: Any) -> str | None:
        if not isinstance(obj, dict):
            return "event must be a JSON object"
        missing = cls.REQUIRED - obj.keys()
        if missing:
            return f"missing fields: {', '.join(sorted(missing))}"
        for key in ("session_id", "utterance_id"):
            if not isinstance(obj[key], str) or not obj[key].strip():
                return f"{key} must be a non-empty string"
        if not isinstance(obj["direction"], str) or obj["direction"] not in cls.DIRECTIONS:
            return "direction must be a2b or b2a"
        if not isinstance(obj["event"], str) or obj["event"] not in cls.EVENTS:
            return f"event must be one of {', '.join(sorted(cls.EVENTS))}"
        timestamp = obj["timestamp_ms"]
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            return "timestamp_ms must be a finite number"
        if not math.isfinite(timestamp) or timestamp < 0:
            return "timestamp_ms must be finite and non-negative"
        if obj["event"] == "capture_end" and obj.get("warm_state") not in cls.WARM_STATES:
            return "capture_end requires warm_state=cold|warm"
        return None


class Harness:
    STAGES = (
        ("capture_to_asr", "capture_end", "asr_end"),
        ("capture_to_nmt", "capture_end", "nmt_end"),
        ("capture_to_first_audio", "capture_end", "first_audio"),
    )

    def __init__(self) -> None:
        self.events: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = {}
        self.errors: list[str] = []
        self.compute_errors: list[str] = []
        self.samples: list[Sample] = []
        self.lines_read = 0

    def ingest_jsonl(self, path: str | Path) -> tuple[int, list[str]]:
        """Ingest one file. Duplicate events are errors, never silently overwritten."""
        self.events.clear()
        self.errors.clear()
        self.compute_errors.clear()
        self.samples.clear()
        self.lines_read = 0
        try:
            with Path(path).open(encoding="utf-8") as source:
                for line_number, raw in enumerate(source, 1):
                    if not raw.strip():
                        continue
                    self.lines_read += 1
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        self.errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
                        continue
                    error = Schema.validate(event)
                    if error:
                        self.errors.append(f"line {line_number}: {error}")
                        continue
                    key = (event["session_id"], event["utterance_id"], event["direction"])
                    bucket = self.events.setdefault(key, {})
                    name = event["event"]
                    if name in bucket:
                        self.errors.append(f"line {line_number}: duplicate {name} for {key}")
                        continue
                    bucket[name] = event
        except OSError as exc:
            self.errors.append(f"cannot read {path}: {exc}")
            return 0, self.errors.copy()
        return self.lines_read, self.errors.copy()

    def compute(self) -> tuple[list[Sample], list[str]]:
        """Compute per-utterance latency; never add stage percentiles to infer E2E."""
        self.samples.clear()
        self.compute_errors.clear()
        errors = self.errors.copy()
        for key, events in sorted(self.events.items()):
            if "capture_end" not in events:
                errors.append(f"{key}: missing capture_end")
                continue
            capture = events["capture_end"]["timestamp_ms"]
            missing = Schema.EVENTS - events.keys()
            if missing:
                errors.append(f"{key}: incomplete utterance, missing {', '.join(sorted(missing))}")
                continue
            stamps = {name: item["timestamp_ms"] for name, item in events.items()}
            ordered = ["capture_end", "asr_end", "nmt_end", "first_audio"]
            if any(stamps[right] < stamps[left] for left, right in zip(ordered, ordered[1:])):
                errors.append(f"{key}: timestamps are not monotonic in pipeline order")
                continue
            self.samples.append(Sample(
                session_id=key[0], utterance_id=key[1], direction=key[2],
                warm_state=events["capture_end"]["warm_state"],
                capture_to_asr_ms=stamps["asr_end"] - capture,
                capture_to_nmt_ms=stamps["nmt_end"] - capture,
                capture_to_first_audio_ms=stamps["first_audio"] - capture,
            ))
        self.compute_errors = errors[len(self.errors):]
        return self.samples.copy(), errors

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        """Linear interpolation on the sorted [0, n-1] index (NumPy default method)."""
        ordered = sorted(values)
        position = (len(ordered) - 1) * percentile / 100
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return float(ordered[lower])
        return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower))

    def summary(self) -> dict[str, Any]:
        summaries = {}
        for direction in ("a2b", "b2a"):
            for state in ("cold", "warm"):
                group = [s for s in self.samples if s.direction == direction and s.warm_state == state]
                if not group:
                    continue
                metrics = {}
                for name, _, _ in self.STAGES:
                    values = [getattr(s, f"{name}_ms") for s in group]
                    metrics[name] = {
                        "n": len(values),
                        "p50_ms": self._percentile(values, 50),
                        "p95_ms": self._percentile(values, 95),
                    }
                summaries[f"{direction}/{state}"] = metrics
        return {
            "schema_version": "vt-latency-events-v1",
            "definition": "capture_end is end of captured source utterance; first_audio is first translated audio rendered at recipient; percentiles computed directly per utterance and are not summed.",
            "lines_read": self.lines_read,
            "samples": len(self.samples),
            "errors": self.errors + self.compute_errors,
            "groups": summaries,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path, help="UTF-8 JSONL event log from a real measured run")
    parser.add_argument("--out", type=Path, help="optional JSON report path")
    args = parser.parse_args()
    harness = Harness()
    harness.ingest_jsonl(args.jsonl)
    _, errors = harness.compute()
    report = harness.summary()
    output = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if args.out:
        args.out.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 1 if errors or not harness.samples else 0


if __name__ == "__main__":
    sys.exit(main())