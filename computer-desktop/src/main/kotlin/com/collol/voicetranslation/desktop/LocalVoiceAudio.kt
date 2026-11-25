package com.collol.voicetranslation.desktop

import javax.sound.sampled.AudioFormat
import javax.sound.sampled.AudioSystem
import javax.sound.sampled.Clip
import javax.sound.sampled.DataLine
import javax.sound.sampled.Line
import javax.sound.sampled.SourceDataLine
import javax.sound.sampled.TargetDataLine
import kotlin.math.abs
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeout

/**
 * What the microphone actually delivered, so the operator can tell a working
 * capture from a muted, wrong-device or permission-blocked one.
 */
internal data class CaptureInfo(
    val device: String,
    val bytes: Int,
    val durationMs: Long,
    val rmsDbfs: Double,
    val peakDbfs: Double,
    val silentRatio: Double,
)

internal class Captured(val pcm: ByteArray, val info: CaptureInfo)

/** What the speaker actually played, so a truncated playback is visible. */
internal data class PlaybackInfo(
    val device: String,
    val bytes: Int,
    val expectedMs: Long,
    val playedMs: Long,
) {
    val complete: Boolean get() = playedMs >= expectedMs - 50
}

internal object LocalVoiceAudio {
    private const val SAMPLE_RATE = 16_000f
    private const val BYTES_PER_MS = 32L
    private const val SILENCE_DBFS = -50.0
    private const val RECORD_BYTES = 4 * 32_000

    private val format = AudioFormat(SAMPLE_RATE, 16, 1, true, false)

    /** Mixer name backing a line class, for diagnostics; never throws. */
    private fun deviceName(lineClass: Class<out Line>, fallback: String): String = runCatching {
        val wanted = DataLine.Info(lineClass, format)
        AudioSystem.getMixerInfo()
            .firstOrNull { AudioSystem.getMixer(it).isLineSupported(wanted) }
            ?.name
    }.getOrNull()?.takeIf { it.isNotBlank() } ?: fallback

    fun inputDevice(): String = deviceName(TargetDataLine::class.java, "microphone unavailable")

    fun outputDevice(): String = deviceName(SourceDataLine::class.java, "speaker unavailable")

    suspend fun record(): Captured {
        val pcm = ByteArray(RECORD_BYTES)
        var device = "default microphone"
        val startedAt = System.nanoTime()
        AudioSystem.getTargetDataLine(format).use { line ->
            device = deviceName(TargetDataLine::class.java, device)
            line.open(format)
            line.start()
            try {
                withTimeout(7_000) {
                    var offset = 0
                    while (offset < pcm.size) {
                        val available = min(line.available(), pcm.size - offset) and -2
                        if (available <= 0) delay(10)
                        else {
                            val read = line.read(pcm, offset, available)
                            check(read > 0) { "Microphone disconnected" }
                            offset += read
                        }
                    }
                }
            } finally {
                line.stop()
            }
        }
        val durationMs = (System.nanoTime() - startedAt) / 1_000_000
        return Captured(pcm, measure(pcm, device, durationMs))
    }

    suspend fun play(pcm: ByteArray): PlaybackInfo {
        require(pcm.isNotEmpty() && pcm.size % 2 == 0) { "playback needs 16-bit PCM" }
        val expectedMs = pcm.size / BYTES_PER_MS
        var device = "default speakers"
        AudioSystem.getClip().use { clip ->
            device = deviceName(Clip::class.java, device)
            clip.open(format, pcm, 0, pcm.size)
            val startedAt = System.nanoTime()
            clip.start()
            withTimeout(expectedMs + 3_000) {
                while (clip.framePosition < clip.frameLength) {
                    delay(20)
                    check(clip.isRunning || clip.framePosition >= clip.frameLength) {
                        "Playback stopped early"
                    }
                }
            }
            clip.stop()
            return PlaybackInfo(device, pcm.size, expectedMs, (System.nanoTime() - startedAt) / 1_000_000)
        }
    }

    /**
     * Speaker regression check that needs no microphone, network or session.
     * A muted machine, wrong output device or detached headset shows up as a
     * short or failed playback instead of a single click.
     */
    suspend fun playTone(durationMs: Int, frequencyHz: Double = 440.0): PlaybackInfo {
        require(durationMs in 200..5_000) { "tone duration out of range" }
        return play(tone(durationMs, frequencyHz))
    }

    private fun tone(durationMs: Int, frequencyHz: Double): ByteArray {
        val samples = durationMs * 16
        val fade = min(samples / 2, 80)
        val pcm = ByteArray(samples * 2)
        for (i in 0 until samples) {
            val envelope = min(1.0, min(i.toDouble() / fade, (samples - 1 - i).toDouble() / fade))
            val value = (6_000 * sin(2 * Math.PI * frequencyHz * i / SAMPLE_RATE) * envelope).toInt()
            pcm[i * 2] = (value and 0xFF).toByte()
            pcm[i * 2 + 1] = ((value shr 8) and 0xFF).toByte()
        }
        return pcm
    }

    private fun measure(pcm: ByteArray, device: String, durationMs: Long): CaptureInfo {
        val frames = pcm.size / 2
        if (frames == 0) return CaptureInfo(device, pcm.size, durationMs, -120.0, -120.0, 1.0)
        val windowFrames = 320  // 20 ms analysis window
        var sumSquares = 0.0
        var peak = 0
        var silentWindows = 0
        var windows = 0
        var windowSum = 0.0
        var windowCount = 0
        for (i in 0 until frames) {
            val sample = ((pcm[i * 2 + 1].toInt() shl 8) or (pcm[i * 2].toInt() and 0xFF)).toShort().toInt()
            val square = sample.toDouble() * sample
            sumSquares += square
            windowSum += square
            windowCount++
            peak = max(peak, abs(sample))
            if (windowCount == windowFrames) {
                windows++
                if (toDbfs(sqrt(windowSum / windowCount)) < SILENCE_DBFS) silentWindows++
                windowSum = 0.0
                windowCount = 0
            }
        }
        if (windowCount > 0) {
            windows++
            if (toDbfs(sqrt(windowSum / windowCount)) < SILENCE_DBFS) silentWindows++
        }
        return CaptureInfo(
            device = device,
            bytes = pcm.size,
            durationMs = durationMs,
            rmsDbfs = toDbfs(sqrt(sumSquares / frames)),
            peakDbfs = toDbfs(peak.toDouble()),
            silentRatio = if (windows == 0) 1.0 else silentWindows.toDouble() / windows,
        )
    }

    private fun toDbfs(amplitude: Double): Double =
        if (amplitude <= 0.0) -120.0 else max(-120.0, 20.0 * log10(amplitude / 32_768.0))

    /** Shared synthetic tone used by the speaker check, exposed for tests. */
    internal fun toneForTest(durationMs: Int, frequencyHz: Double = 440.0): ByteArray =
        tone(durationMs, frequencyHz)

    /** Shared capture statistics, exposed for tests without touching a device. */
    internal fun measureForTest(pcm: ByteArray): CaptureInfo = measure(pcm, "test", 0L)
}