package com.collol.voicetranslation.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.SystemClock
import com.collol.voicetranslation.service.CaptureResource
import java.util.concurrent.atomic.AtomicBoolean

interface AudioRecordPort {
    val recordingState: Int
    fun startRecording()
    fun stop()
    fun read(buffer: ByteArray, offset: Int, size: Int): Int
    fun release()
}

private class PlatformAudioRecordPort(private val record: AudioRecord) : AudioRecordPort {
    override val recordingState: Int
        get() = record.recordingState

    override fun startRecording() = record.startRecording()

    override fun stop() = record.stop()

    override fun read(buffer: ByteArray, offset: Int, size: Int): Int =
        record.read(buffer, offset, size, AudioRecord.READ_BLOCKING)

    override fun release() = record.release()
}

fun interface PcmChunkSink {
    fun onChunk(chunk: CapturedPcmChunk)
}

/** Blocking microphone reader. It owns AudioRecord and never writes audio to disk. */
class AudioRecordCapture(
    private val audioRecord: AudioRecordPort,
    private val format: PcmFormat = DEFAULT_FORMAT,
    private val monotonicNanos: () -> Long = SystemClock::elapsedRealtimeNanos,
    private val chunkSink: PcmChunkSink,
    private val onCaptureTerminated: () -> Unit = {},
) : CaptureResource {
    private val running = AtomicBoolean(false)
    private val releaseRequested = AtomicBoolean(false)
    private val released = AtomicBoolean(false)
    private val worker = Thread(::readLoop, "voice-translation-audio-capture")
    private val timestampTracker = PcmTimestampTracker(format)
    private val buffer = ByteArray(CHUNK_FRAMES * format.bytesPerFrame)

    override fun start() {
        check(running.compareAndSet(false, true)) { "capture already started" }
        try {
            audioRecord.startRecording()
            if (audioRecord.recordingState != AudioRecord.RECORDSTATE_RECORDING) {
                error("AudioRecord did not enter recording state")
            }
            worker.start()
        } catch (cause: Throwable) {
            running.set(false)
            runCatching { audioRecord.stop() }
            throw cause
        }
    }

    override fun stop() {
        if (!running.getAndSet(false)) return
        runCatching { audioRecord.stop() }
        if (Thread.currentThread() !== worker) {
            runCatching { worker.join(JOIN_TIMEOUT_MILLIS) }
        }
    }

    override fun release() {
        releaseRequested.set(true)
        stop()
        if (!worker.isAlive) releaseAudioRecord()
    }

    private fun readLoop() {
        try {
            while (running.get()) {
                val bytesRead = audioRecord.read(buffer, 0, buffer.size)
                val completedAtNanos = monotonicNanos()
                if (bytesRead <= 0 || bytesRead % format.bytesPerFrame != 0) {
                    break
                }

                val sampleCount = bytesRead / format.bytesPerSample
                val timestamp = try {
                    timestampTracker.next(sampleCount, completedAtNanos)
                } catch (_: IllegalArgumentException) {
                    break
                }
                val pcm = buffer.copyOf(bytesRead)
                try {
                    chunkSink.onChunk(
                        CapturedPcmChunk(
                            sequence = timestamp.sequence,
                            format = format,
                            pcm = pcm,
                            captureTimeNanos = timestamp.captureTimeNanos,
                            durationNanos = timestamp.durationNanos,
                            readCompletedAtNanos = timestamp.readCompletedAtNanos,
                        ),
                    )
                } catch (_: Throwable) {
                    break
                }
            }
        } finally {
            if (running.getAndSet(false)) onCaptureTerminated()
            if (releaseRequested.get()) releaseAudioRecord()
        }
    }

    private fun releaseAudioRecord() {
        if (released.compareAndSet(false, true)) audioRecord.release()
    }

    companion object {
        const val SAMPLE_RATE_HZ = 16_000
        const val CHANNEL_COUNT = 1
        const val BITS_PER_SAMPLE = 16
        const val CHUNK_FRAMES = 320
        private const val JOIN_TIMEOUT_MILLIS = 500L
        val DEFAULT_FORMAT = PcmFormat(SAMPLE_RATE_HZ, CHANNEL_COUNT, BITS_PER_SAMPLE)

        fun create(
            chunkSink: PcmChunkSink,
            onCaptureTerminated: () -> Unit = {},
            audioRecordFactory: (sampleRateHz: Int, channelMask: Int, encoding: Int, bufferSize: Int) -> AudioRecord =
                ::createAudioRecord,
        ): AudioRecordCapture {
            val format = DEFAULT_FORMAT
            val channelMask = AudioFormat.CHANNEL_IN_MONO
            val encoding = AudioFormat.ENCODING_PCM_16BIT
            val minimumBuffer = AudioRecord.getMinBufferSize(format.sampleRateHz, channelMask, encoding)
            require(minimumBuffer > 0) { "AudioRecord minimum buffer size is invalid: $minimumBuffer" }
            val bufferSize = maxOf(minimumBuffer, CHUNK_FRAMES * format.bytesPerFrame * 2)
            return AudioRecordCapture(
                audioRecord = PlatformAudioRecordPort(
                    audioRecordFactory(format.sampleRateHz, channelMask, encoding, bufferSize),
                ),
                format = format,
                chunkSink = chunkSink,
                onCaptureTerminated = onCaptureTerminated,
            )
        }

        @SuppressLint("MissingPermission")
        private fun createAudioRecord(
            sampleRateHz: Int,
            channelMask: Int,
            encoding: Int,
            bufferSize: Int,
        ): AudioRecord = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            sampleRateHz,
            channelMask,
            encoding,
            bufferSize,
        )
    }
}
