package com.collol.voicetranslation.desktop

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertTrue

class SessionClientTest {
    @Test
    fun bothUtteranceDirectionsReturnPcmAgainstLocalBackend() {
        val url = System.getenv("VOICE_DESKTOP_TEST_URL") ?: return
        BackendClient(url).start("vi", "en").use { session ->
            assertTrue(session.supportsUtterances)
            assertEquals("fake", session.provider)
            repeat(2) {
                for (stream in listOf("a2b", "b2a")) {
                    val audio = session.translateUtterance(stream, ByteArray(1280))
                    assertTrue(audio.size > 640 && audio.size % 2 == 0)
                }
            }
            session.cancel()
        }
    }

    @Test
    fun backendUnreachableFailsInsteadOfReturningAnActiveSession() {
        assertFails { BackendClient("http://127.0.0.1:1").start("vi", "en") }
    }

    @Test
    fun startAndStopAgainstLocalBackendWhenRequested() {
        val url = System.getenv("VOICE_DESKTOP_TEST_URL") ?: return
        val client = BackendClient(url)
        assertTrue(client.health())
        client.start("vi", "en").use { session ->
            assertTrue(session.id.isNotBlank())
            session.cancel()
        }
        assertFails { client.start("", "en") }
        client.start("en", "vi").use { it.cancel() }
    }

    @Test
    fun settingsPersistAcrossClientInstances() {
        val url = System.getenv("VOICE_DESKTOP_TEST_URL") ?: return
        val original = BackendClient(url).loadSettings()
        try {
            val changed = LanguageSettings("en", "vi")
            BackendClient(url).saveSettings(changed)
            assertEquals(changed, BackendClient(url).loadSettings())
        } finally {
            BackendClient(url).saveSettings(original)
        }
    }
}
