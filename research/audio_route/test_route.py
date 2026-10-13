"""Fake-media tests for the two device-A VoIP hooks. Not a real call or device proof."""
from __future__ import annotations

import unittest

from research.audio_route.route_harness import RouteError, TranslationRoute

PCM_A = b"\x01\x02\x03\x04"   # synthetic; never real microphone audio
PCM_B = b"\x0a\x0b\x0c\x0d"   # synthetic; never real peer audio
TRANSLATED_A = b"\x20\x21\x22\x23"
TRANSLATED_B = b"\x30\x31\x32\x33"


def translator(payload: bytes, direction: str) -> bytes:
    return TRANSLATED_A if direction == "a2b" else TRANSLATED_B


class PassthroughTests(unittest.TestCase):
    def test_inactive_call_is_untouched(self):
        route = TranslationRoute(translator)
        self.assertEqual(route.outbound_from_mic_a(PCM_A, 0), PCM_A)
        self.assertEqual(route.inbound_from_peer_b(PCM_B, 0), PCM_B)
        self.assertEqual(route.counters("a2b").raw_frames, 1)
        self.assertEqual(route.counters("b2a").raw_frames, 1)

    def test_empty_frame_is_dropped_not_forwarded(self):
        route = TranslationRoute(translator)
        self.assertIsNone(route.outbound_from_mic_a(b"", 0))
        self.assertEqual(route.counters("a2b").dropped_frames, 1)


class SubstitutionTests(unittest.TestCase):
    def setUp(self):
        self.route = TranslationRoute(translator)
        self.route.start()

    def test_outbound_carries_only_translation(self):
        self.assertEqual(self.route.outbound_from_mic_a(PCM_A, 0), TRANSLATED_A)

    def test_inbound_render_carries_only_translation(self):
        self.assertEqual(self.route.inbound_from_peer_b(PCM_B, 0), TRANSLATED_B)

    def test_directions_keep_separate_counters(self):
        self.route.outbound_from_mic_a(PCM_A, 0)
        self.route.outbound_from_mic_a(PCM_A, 1)
        self.route.inbound_from_peer_b(PCM_B, 0)
        self.assertEqual(self.route.counters("a2b").translated_frames, 2)
        self.assertEqual(self.route.counters("b2a").translated_frames, 1)

    def test_stale_and_duplicate_frames_are_rejected(self):
        self.route.outbound_from_mic_a(PCM_A, 5)
        with self.assertRaises(RouteError):
            self.route.outbound_from_mic_a(PCM_A, 5)
        self.route.inbound_from_peer_b(PCM_B, 4)
        with self.assertRaises(RouteError):
            self.route.inbound_from_peer_b(PCM_B, 4)

    def test_sequence_numbers_are_tracked_per_direction(self):
        self.route.outbound_from_mic_a(PCM_A, 7)
        self.route.inbound_from_peer_b(PCM_B, 1)
        self.assertEqual(self.route.counters("a2b").last_seq, 7)
        self.assertEqual(self.route.counters("b2a").last_seq, 1)

    def test_translation_failure_never_leaks_raw_audio(self):
        def failing(payload: bytes, direction: str) -> bytes:
            raise RuntimeError("ASR/NMT/TTS unavailable")
        route = TranslationRoute(failing)
        route.start()
        self.assertIsNone(route.outbound_from_mic_a(PCM_A, 0))
        self.assertIsNone(route.inbound_from_peer_b(PCM_B, 0))
        self.assertEqual(route.counters("a2b").dropped_frames, 1)
        self.assertEqual(route.counters("b2a").dropped_frames, 1)

    def test_empty_translation_never_leaks_raw_audio(self):
        route = TranslationRoute(lambda payload, direction: b"")
        route.start()
        self.assertIsNone(route.outbound_from_mic_a(PCM_A, 0))

    def test_non_bytes_payload_is_rejected(self):
        with self.assertRaises(RouteError):
            self.route.outbound_from_mic_a("not-bytes", 0)
        with self.assertRaises(RouteError):
            self.route.inbound_from_peer_b(PCM_B, True)


class LifecycleTests(unittest.TestCase):
    def test_stop_returns_call_to_plain_audio(self):
        route = TranslationRoute(translator)
        route.start()
        route.outbound_from_mic_a(PCM_A, 0)
        route.stop()
        self.assertEqual(route.outbound_from_mic_a(PCM_A, 0), PCM_A)
        self.assertEqual(route.counters("a2b").raw_frames, 1)
        self.assertEqual(route.counters("a2b").last_seq, 0)

    def test_stop_clears_stale_sequence_state_for_next_call(self):
        route = TranslationRoute(translator)
        route.start()
        route.outbound_from_mic_a(PCM_A, 99)
        route.stop()
        route.start()
        self.assertEqual(route.outbound_from_mic_a(PCM_A, 0), TRANSLATED_A)

    def test_direction_must_be_known(self):
        route = TranslationRoute(translator)
        with self.assertRaises(RouteError):
            route.counters("a2c")


if __name__ == "__main__":
    unittest.main()