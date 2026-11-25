package com.collol.voicetranslation.desktop

import javax.sound.sampled.AudioFormat
import javax.sound.sampled.AudioSystem
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeout

internal object LocalVoiceAudio {
    private val format = AudioFormat(16_000f, 16, 1, true, false)
    private const val RECORD_BYTES = 4 * 32_000

    suspend fun record(): ByteArray {
        val pcm = ByteArray(RECORD_BYTES)
        AudioSystem.getTargetDataLine(format).use { line ->
            line.open(format)
            line.start()
            withTimeout(7_000) {
                var offset = 0
                while (offset < pcm.size) {
                    val available = minOf(line.available(), pcm.size - offset) and -2
                    if (available == 0) delay(10)
                    else {
                        val read = line.read(pcm, offset, available)
                        check(read > 0) { "Microphone disconnected" }
                        offset += read
                    }
                }
            }
        }
        return pcm
    }

    suspend fun play(pcm: ByteArray) {
        AudioSystem.getClip().use { clip ->
            clip.open(format, pcm, 0, pcm.size)
            clip.start()
            withTimeout(pcm.size / 32L + 3_000) {
                while (clip.framePosition < clip.frameLength) {
                    delay(20)
                    check(clip.isRunning || clip.framePosition >= clip.frameLength) { "Playback stopped early" }
                }
            }
        }
    }
}
