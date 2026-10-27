package com.collol.voicetranslation.audio

/** PCM contract shared by capture and the future controlled media transport. */
data class PcmFormat(
    val sampleRateHz: Int,
    val channelCount: Int,
    val bitsPerSample: Int,
) {
    init {
        require(sampleRateHz > 0) { "sampleRateHz must be positive" }
        require(channelCount > 0) { "channelCount must be positive" }
        require(bitsPerSample == 16) { "only signed 16-bit PCM is supported" }
    }

    val bytesPerSample: Int = bitsPerSample / 8
    val bytesPerFrame: Int = bytesPerSample * channelCount

    fun durationNanos(frameCount: Int): Long {
        require(frameCount >= 0) { "frameCount must not be negative" }
        return frameCount.toLong() * NANOS_PER_SECOND / sampleRateHz
    }

    companion object {
        private const val NANOS_PER_SECOND = 1_000_000_000L
    }
}

data class CapturedPcmChunk(
    val sequence: Long,
    val format: PcmFormat,
    val pcm: ByteArray,
    val captureTimeNanos: Long,
    val durationNanos: Long,
    val readCompletedAtNanos: Long,
) {
    init {
        require(pcm.isNotEmpty()) { "pcm must not be empty" }
        require(pcm.size % format.bytesPerFrame == 0) { "pcm must contain complete frames" }
        require(captureTimeNanos >= 0) { "captureTimeNanos must not be negative" }
        require(durationNanos > 0) { "durationNanos must be positive" }
        require(readCompletedAtNanos >= captureTimeNanos) {
            "readCompletedAtNanos must not precede captureTimeNanos"
        }
    }
}

class PcmTimestampTracker(private val format: PcmFormat) {
    private var nextSequence = 0L
    private var nextCaptureTimeNanos: Long? = null
    private var lastReadCompletedAtNanos = Long.MIN_VALUE

    fun next(sampleCount: Int, readCompletedAtNanos: Long): CapturedPcmTimestamp {
        require(sampleCount > 0) { "sampleCount must be positive" }
        require(sampleCount % format.channelCount == 0) { "sampleCount must contain complete frames" }
        require(readCompletedAtNanos >= 0) { "readCompletedAtNanos must not be negative" }
        require(readCompletedAtNanos >= lastReadCompletedAtNanos) {
            "monotonic clock moved backwards"
        }

        val frameCount = sampleCount / format.channelCount
        val durationNanos = format.durationNanos(frameCount)
        val captureTimeNanos = nextCaptureTimeNanos
            ?: (readCompletedAtNanos - durationNanos).coerceAtLeast(0L)
        nextCaptureTimeNanos = captureTimeNanos + durationNanos
        lastReadCompletedAtNanos = readCompletedAtNanos

        return CapturedPcmTimestamp(
            sequence = nextSequence++,
            captureTimeNanos = captureTimeNanos,
            durationNanos = durationNanos,
            readCompletedAtNanos = readCompletedAtNanos,
        )
    }
}

data class CapturedPcmTimestamp(
    val sequence: Long,
    val captureTimeNanos: Long,
    val durationNanos: Long,
    val readCompletedAtNanos: Long,
)
