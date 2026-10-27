package com.collol.voicetranslation.developer

/** Summary of successful model translation latency samples. */
data class ModelBenchmarkSummary(
    val sampleCount: Int,
    val failedCount: Int,
    val minMillis: Long,
    val medianMillis: Double,
    val meanMillis: Double,
    val p95Millis: Long,
)

object ModelBenchmarkStats {
    fun summarize(samplesMillis: List<Long>, failedCount: Int): ModelBenchmarkSummary? {
        if (samplesMillis.isEmpty()) return null
        require(samplesMillis.all { it >= 0 }) { "Latency samples must be non-negative" }
        require(failedCount >= 0) { "Failure count must be non-negative" }

        val sorted = samplesMillis.sorted()
        val middle = sorted.size / 2
        val median = if (sorted.size % 2 == 0) {
            (sorted[middle - 1].toDouble() + sorted[middle].toDouble()) / 2.0
        } else {
            sorted[middle].toDouble()
        }
        val p95 = percentileNearestRank(sorted, 0.95)
        return ModelBenchmarkSummary(
            sampleCount = sorted.size,
            failedCount = failedCount,
            minMillis = sorted.first(),
            medianMillis = median,
            meanMillis = sorted.average(),
            p95Millis = p95,
        )
    }

    private fun percentileNearestRank(sorted: List<Long>, percentile: Double): Long {
        val rank = kotlin.math.ceil(percentile * sorted.size).toInt().coerceAtLeast(1)
        return sorted[rank - 1]
    }
}
