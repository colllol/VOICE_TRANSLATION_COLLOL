package com.collol.voicetranslation.desktop

import kotlin.test.Test
import kotlin.test.assertFalse

class BackendClientTest {
    @Test
    fun healthIsFalseWhenBackendIsUnavailable() {
        assertFalse(BackendClient("http://127.0.0.1:1").health())
    }
}
