package com.collol.voicetranslation.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.util.concurrent.atomic.AtomicBoolean

/** Reads short PCM windows for developer diagnostics without persisting audio. */
class AudioDiagnosticsRecorder(
    private val onMetrics: (AudioMetrics) -> Unit,
    private val onFailure: (Throwable) -> Unit,
) {
    private val running = AtomicBoolean(false)
    private var recorder: AudioRecord? = null
    private var worker: Thread? = null

    @SuppressLint("MissingPermission")
    fun start() {
        check(running.compareAndSet(false, true)) { "diagnostics already running" }
        try {
            val minimumBuffer = AudioRecord.getMinBufferSize(
                SAMPLE_RATE_HZ,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
            )
            require(minimumBuffer > 0) { "invalid AudioRecord buffer size: $minimumBuffer" }
            val audioRecord = AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                SAMPLE_RATE_HZ,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                maxOf(minimumBuffer, WINDOW_SAMPLES * BYTES_PER_SAMPLE * 2),
            )
            recorder = audioRecord
            audioRecord.startRecording()
            check(audioRecord.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                "AudioRecord did not enter recording state"
            }
            worker = Thread(::readLoop, "voice-translation-developer-metrics").also { it.start() }
        } catch (cause: Throwable) {
            running.set(false)
            recorder?.release()
            recorder = null
            onFailure(cause)
        }
    }

    fun stop() {
        if (!running.getAndSet(false)) return
        runCatching { recorder?.stop() }
        if (Thread.currentThread() !== worker) {
            runCatching { worker?.join(JOIN_TIMEOUT_MILLIS) }
        }
        runCatching { recorder?.release() }
        recorder = null
        worker = null
    }

    private fun readLoop() {
        val buffer = ByteArray(WINDOW_SAMPLES * BYTES_PER_SAMPLE)
        try {
            while (running.get()) {
                val count = recorder?.read(buffer, 0, buffer.size, AudioRecord.READ_BLOCKING) ?: 0
                if (count <= 0) continue
                val samples = ShortArray(count / BYTES_PER_SAMPLE)
                for (index in samples.indices) {
                    val offset = index * BYTES_PER_SAMPLE
                    samples[index] = ((buffer[offset].toInt() and 0xff) or
                        (buffer[offset + 1].toInt() shl 8)).toShort()
                }
                onMetrics(AudioMetricsCalculator.analyze(samples, SAMPLE_RATE_HZ))
            }
        } catch (cause: Throwable) {
            if (running.get()) onFailure(cause)
        }
    }

    companion object {
        const val SAMPLE_RATE_HZ = 16_000
        private const val WINDOW_SAMPLES = 1024
        private const val BYTES_PER_SAMPLE = 2
        private const val JOIN_TIMEOUT_MILLIS = 500L
    }
}
