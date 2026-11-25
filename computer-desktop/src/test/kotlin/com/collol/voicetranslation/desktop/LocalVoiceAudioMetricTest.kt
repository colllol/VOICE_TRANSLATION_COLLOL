package com.collol.voicetranslation.desktop

import kotlin.math.abs
import kotlin.math.sin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * The numbers the operator sees must come from the captured samples, so these
 * tests pin the measurement maths without touching a real audio device.
 */
class LocalVoiceAudioMetricTest {

    private fun alternatingFullScale(frames: Int): ByteArray {
        val pcm = ByteArray(frames * 2)
        for (i in 0 until frames) {
            val value = if (i % 2 == 0) 32_767 else -32_768
            pcm[i * 2] = (value and 0xFF).toByte()
            pcm[i * 2 + 1] = ((value shr 8) and 0xFF).toByte()
        }
        return pcm
    }

    @Test
    fun silentCaptureIsReportedAsSilent() {
        val info = LocalVoiceAudio.measureForTest(ByteArray(32_000))

        assertEquals(32_000, info.bytes)
        assertEquals(1.0, info.silentRatio)
        assertEquals(-120.0, info.rmsDbfs)
        assertEquals(-120.0, info.peakDbfs)
    }

    @Test
    fun fullScaleCaptureReachesZeroDbfs() {
        val info = LocalVoiceAudio.measureForTest(alternatingFullScale(320))

        assertTrue(abs(info.peakDbfs) < 0.1, "peak was ${info.peakDbfs}")
        assertTrue(info.rmsDbfs > -1.0, "rms was ${info.rmsDbfs}")
        assertEquals(0.0, info.silentRatio)
    }

    @Test
    fun halfSilentCaptureReportsHalfTheWindows() {
        val pcm = alternatingFullScale(320) + ByteArray(640)  // 20 ms tone, 20 ms silence

        val info = LocalVoiceAudio.measureForTest(pcm)

        assertEquals(0.5, info.silentRatio)
        assertTrue(info.rmsDbfs in -4.0..-2.0, "rms was ${info.rmsDbfs}")
    }

    @Test
    fun quietRoomIsNotMistakenForSilence() {
        // ~ -40 dBFS: audible speech at a normal distance, well above the gate.
        val pcm = ByteArray(32_000)
        for (i in 0 until 16_000) {
            val value = (328.0 * sin(2 * Math.PI * 300 * i / 16_000)).toInt()
            pcm[i * 2] = (value and 0xFF).toByte()
            pcm[i * 2 + 1] = ((value shr 8) and 0xFF).toByte()
        }

        val info = LocalVoiceAudio.measureForTest(pcm)

        assertTrue(info.rmsDbfs in -45.0..-35.0, "rms was ${info.rmsDbfs}")
        assertEquals(0.0, info.silentRatio)
    }

    @Test
    fun generatedToneHasTheRequestedDuration() {
        val pcm = LocalVoiceAudio.toneForTest(1_000)

        assertEquals(32_000, pcm.size)  // 1 s at 16 kHz mono s16le
        assertTrue(pcm.any { it != 0.toByte() })
        // The 5 ms fades keep the first and last samples at zero to avoid pops.
        assertEquals(0.toByte(), pcm[0])
        assertEquals(0.toByte(), pcm[pcm.size - 1])
    }
}