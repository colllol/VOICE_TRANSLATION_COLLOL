package com.collol.voicetranslation.developer

import org.junit.Assert.assertEquals
import org.junit.Test

class ModelBenchmarkStatsTest {
    @Test
    fun `summarizes latency samples with nearest rank p95`() {
        val summary = ModelBenchmarkStats.summarize(
            samplesMillis = listOf(10L, 20L, 30L, 40L, 100L),
            failedCount = 1,
        )

        val actual = summary ?: error("Expected successful benchmark summary")
        assertEquals(5, actual.sampleCount)
        assertEquals(1, actual.failedCount)
        assertEquals(10L, actual.minMillis)
        assertEquals(30.0, actual.medianMillis, 0.0001)
        assertEquals(40.0, actual.meanMillis, 0.0001)
        assertEquals(100L, actual.p95Millis)
    }

    @Test
    fun `median averages the two center samples for even sample counts`() {
        val summary = ModelBenchmarkStats.summarize(listOf(10L, 20L, 30L, 40L), failedCount = 0)

        val actual = summary ?: error("Expected successful benchmark summary")
        assertEquals(25.0, actual.medianMillis, 0.0001)
    }

    @Test
    fun `rejects empty successful sample set`() {
        val summary = ModelBenchmarkStats.summarize(emptyList(), failedCount = 2)

        assertEquals(null, summary)
    }
}
