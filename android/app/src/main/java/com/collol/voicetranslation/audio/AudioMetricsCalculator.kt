package com.collol.voicetranslation.audio

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.sin
import kotlin.math.sqrt

data class AudioMetrics(
    val rms: Double,
    val peak: Double,
    val dominantFrequencyHz: Int,
)

/** Lightweight diagnostics for signed mono PCM16 chunks. */
object AudioMetricsCalculator {
    fun analyze(samples: ShortArray, sampleRateHz: Int): AudioMetrics {
        require(sampleRateHz > 0) { "sampleRateHz must be positive" }
        if (samples.isEmpty()) return AudioMetrics(0.0, 0.0, 0)

        var sumSquares = 0.0
        var peak = 0.0
        samples.forEach { sample ->
            val normalized = abs(sample.toInt()) / 32768.0
            sumSquares += normalized * normalized
            peak = max(peak, normalized)
        }
        val rms = sqrt(sumSquares / samples.size)
        if (peak < 0.001) return AudioMetrics(rms, peak, 0)

        val windowSize = minOf(samples.size, 1024)
        val binLimit = windowSize / 2
        val windowedSamples = DoubleArray(windowSize) { index ->
            val window = if (windowSize > 1) {
                0.54 - 0.46 * kotlin.math.cos(2.0 * PI * index / (windowSize - 1))
            } else {
                1.0
            }
            samples[index].toInt() / 32768.0 * window
        }
        var bestBin = 0
        var bestMagnitude = 0.0
        for (bin in 1..binLimit) {
            val coefficient = 2.0 * kotlin.math.cos(2.0 * PI * bin / windowSize)
            var previous = 0.0
            var previousPrevious = 0.0
            for (index in 0 until windowSize) {
                val current = windowedSamples[index] + coefficient * previous - previousPrevious
                previousPrevious = previous
                previous = current
            }
            val magnitude = previous * previous + previousPrevious * previousPrevious - coefficient * previous * previousPrevious
            if (magnitude > bestMagnitude) {
                bestMagnitude = magnitude
                bestBin = bin
            }
        }
        return AudioMetrics(rms, peak, bestBin * sampleRateHz / windowSize)
    }
}
