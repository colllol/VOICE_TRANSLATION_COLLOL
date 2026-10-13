"""Regression tests for the instrumentation-only latency harness."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.models.benchmark_harness import Harness, Schema


def events(session: str, utterance: str, direction: str, base: int,
           delta: int, state: str = "cold") -> list[dict]:
    """Synthetic timestamps only; not measured inference data."""
    return [
        {"session_id": session, "utterance_id": utterance, "direction": direction,
         "event": event, "timestamp_ms": base + offset,
         **({"warm_state": state} if event == "capture_end" else {})}
        for event, offset in (("capture_end", 0), ("asr_end", delta // 3),
                              ("nmt_end", delta * 2 // 3), ("first_audio", delta))
    ]


def run_events(lines: list[object]) -> tuple[Harness, list[str]]:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "events.jsonl"
        path.write_text("\n".join(json.dumps(x) if isinstance(x, dict) else str(x)
                                   for x in lines) + "\n", encoding="utf-8")
        harness = Harness()
        harness.ingest_jsonl(path)
        _, errors = harness.compute()
        return harness, errors


class HarnessTests(unittest.TestCase):
    def test_two_directions_and_two_utterances_per_session(self):
        data = (events("s1", "a-1", "a2b", 100, 300) +
                events("s1", "a-2", "a2b", 1000, 600, "warm") +
                events("s1", "b-1", "b2a", 150, 450))
        harness, errors = run_events(data)
        self.assertEqual(errors, [])
        self.assertEqual(len(harness.samples), 3)
        self.assertEqual(set(harness.summary()["groups"]),
                         {"a2b/cold", "a2b/warm", "b2a/cold"})
        self.assertEqual(harness.summary()["groups"]["a2b/warm"]["capture_to_first_audio"]["p95_ms"], 600)

    def test_true_e2e_percentile_not_sum_of_stage_percentiles(self):
        data = []
        for n, duration in enumerate((100, 200, 300, 400, 900)):
            data += events("s", f"u{n}", "a2b", n * 2000, duration, "warm")
        harness, errors = run_events(data)
        self.assertEqual(errors, [])
        metrics = harness.summary()["groups"]["a2b/warm"]
        self.assertEqual(metrics["capture_to_first_audio"]["n"], 5)
        self.assertEqual(metrics["capture_to_first_audio"]["p50_ms"], 300)
        self.assertAlmostEqual(metrics["capture_to_first_audio"]["p95_ms"], 800)
        self.assertNotEqual(metrics["capture_to_first_audio"]["p95_ms"],
                            metrics["capture_to_asr"]["p95_ms"] +
                            metrics["capture_to_nmt"]["p95_ms"])

    def test_duplicate_event_is_error_not_last_wins(self):
        data = events("s", "u", "a2b", 100, 300)
        harness, errors = run_events(data + [data[0]])
        self.assertTrue(any("duplicate capture_end" in error for error in errors))
        self.assertEqual(len(harness.samples), 1)

    def test_nonmonotonic_pipeline_is_error(self):
        data = events("s", "u", "a2b", 100, 300)
        data[1]["timestamp_ms"] = 250
        data[2]["timestamp_ms"] = 200
        harness, errors = run_events(data)
        self.assertTrue(any("not monotonic" in error for error in errors))
        self.assertEqual(harness.samples, [])

    def test_incomplete_utterance_is_error(self):
        harness, errors = run_events(events("s", "u", "b2a", 100, 300)[:-1])
        self.assertTrue(any("incomplete utterance" in error for error in errors))
        self.assertEqual(harness.samples, [])

    def test_missing_capture_is_error(self):
        harness, errors = run_events(events("s", "u", "b2a", 100, 300)[1:])
        self.assertTrue(any("missing capture_end" in error for error in errors))
        self.assertEqual(harness.samples, [])

    def test_events_can_arrive_out_of_timestamp_order(self):
        data = list(reversed(events("s", "u", "b2a", 100, 300)))
        harness, errors = run_events(data)
        self.assertEqual(errors, [])
        self.assertEqual(harness.samples[0].capture_to_first_audio_ms, 300)

    def test_malformed_and_invalid_schema(self):
        data = events("s", "u", "a2b", 100, 300) + ["{broken", {"session_id": "s"}]
        harness, errors = run_events(data)
        self.assertEqual(len(errors), 2)
        self.assertEqual(len(harness.samples), 1)

    def test_invalid_timestamp_values_and_state(self):
        good = events("s", "u", "a2b", 100, 300)[0]
        for value in (True, -1, float("inf"), "5"):
            invalid = {**good, "timestamp_ms": value}
            self.assertIsNotNone(Schema.validate(invalid))
        self.assertIsNotNone(Schema.validate({**good, "warm_state": "maybe"}))
        self.assertIsNotNone(Schema.validate({**good, "direction": "x2y"}))

    def test_empty_input_has_no_metrics(self):
        harness, errors = run_events([])
        self.assertEqual(errors, [])
        self.assertEqual(harness.samples, [])
        self.assertEqual(harness.summary()["groups"], {})


if __name__ == "__main__":
    unittest.main()