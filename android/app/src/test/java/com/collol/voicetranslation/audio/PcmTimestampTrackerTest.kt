package com.collol.voicetranslation.audio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PcmTimestampTrackerTest {
    private val format = PcmFormat(
        sampleRateHz = 16_000,
        channelCount = 1,
        bitsPerSample = 16,
    )

    @Test
    fun `format describes mono 16-bit PCM frame sizes`() {
        assertEquals(2, format.bytesPerFrame)
        assertEquals(20_000_000L, format.durationNanos(frameCount = 320))
    }

    @Test(expected = IllegalArgumentException::class)
    fun `format rejects unsupported sample widths`() {
        PcmFormat(sampleRateHz = 16_000, channelCount = 1, bitsPerSample = 24)
    }

    @Test
    fun `tracker assigns contiguous monotonic timestamps from frame counts`() {
        val tracker = PcmTimestampTracker(format)

        val first = tracker.next(sampleCount = 320, readCompletedAtNanos = 1_000_000_000L)
        val second = tracker.next(sampleCount = 160, readCompletedAtNanos = 1_040_000_000L)

        assertEquals(0L, first.sequence)
        assertEquals(980_000_000L, first.captureTimeNanos)
        assertEquals(20_000_000L, first.durationNanos)
        assertEquals(1_000_000_000L, first.readCompletedAtNanos)
        assertEquals(1L, second.sequence)
        assertEquals(first.captureTimeNanos + first.durationNanos, second.captureTimeNanos)
        assertEquals(10_000_000L, second.durationNanos)
        assertTrue(second.readCompletedAtNanos >= second.captureTimeNanos)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `tracker rejects partial interleaved frames`() {
        val stereo = PcmFormat(sampleRateHz = 16_000, channelCount = 2, bitsPerSample = 16)

        PcmTimestampTracker(stereo).next(sampleCount = 3, readCompletedAtNanos = 1L)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `tracker rejects a regressing monotonic clock`() {
        val tracker = PcmTimestampTracker(format)
        tracker.next(sampleCount = 160, readCompletedAtNanos = 1_000_000_000L)

        tracker.next(sampleCount = 160, readCompletedAtNanos = 999_999_999L)
    }
}
