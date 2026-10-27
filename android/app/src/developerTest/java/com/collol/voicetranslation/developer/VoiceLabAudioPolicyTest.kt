package com.collol.voicetranslation.developer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceLabAudioPolicyTest {
    @Test
    fun `stale callbacks are rejected after a new run starts`() {
        assertTrue(VoiceLabAudioPolicy.isCurrentRun(candidate = 7L, current = 7L, running = true))
        assertTrue(!VoiceLabAudioPolicy.isCurrentRun(candidate = 6L, current = 7L, running = true))
        assertTrue(!VoiceLabAudioPolicy.isCurrentRun(candidate = 7L, current = 7L, running = false))
    }

    @Test
    fun `stale translation callbacks are rejected after a newer utterance`() {
        assertTrue(VoiceLabAudioPolicy.isCurrentUtterance(candidate = 12L, current = 12L))
        assertTrue(!VoiceLabAudioPolicy.isCurrentUtterance(candidate = 11L, current = 12L))
    }

    @Test
    fun `speech RMS dB is normalized for the diagnostics panel`() {
        assertEquals(1.0, VoiceLabAudioPolicy.normalizedRmsFromSpeechDb(0f), 0.0001)
        assertEquals(0.1, VoiceLabAudioPolicy.normalizedRmsFromSpeechDb(-20f), 0.0001)
        assertEquals(0.0, VoiceLabAudioPolicy.normalizedRmsFromSpeechDb(Float.NaN), 0.0001)
    }
}
