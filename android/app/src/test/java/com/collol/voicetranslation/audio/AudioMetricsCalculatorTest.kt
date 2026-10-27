package com.collol.voicetranslation.audio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.PI
import kotlin.math.sin

class AudioMetricsCalculatorTest {
    @Test
    fun `silence has zero level and no dominant frequency`() {
        val metrics = AudioMetricsCalculator.analyze(ShortArray(1024), 16_000)

        assertEquals(0.0, metrics.rms, 0.0001)
        assertEquals(0.0, metrics.peak, 0.0001)
        assertEquals(0, metrics.dominantFrequencyHz)
    }

    @Test
    fun `sine wave reports level and dominant frequency`() {
        val sampleRate = 16_000
        val frequency = 1_000
        val samples = ShortArray(1024) { index ->
            (Short.MAX_VALUE * 0.5 * sin(2.0 * PI * frequency * index / sampleRate)).toInt().toShort()
        }

        val metrics = AudioMetricsCalculator.analyze(samples, sampleRate)

        assertTrue(metrics.rms > 0.30)
        assertTrue(metrics.peak > 0.49)
        assertTrue(kotlin.math.abs(metrics.dominantFrequencyHz - frequency) <= 32)
    }
}
