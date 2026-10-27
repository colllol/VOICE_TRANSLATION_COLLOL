package com.collol.voicetranslation.service

import org.junit.Assert.assertEquals
import org.junit.Test

class CaptureUiStatusTest {
    @Test
    fun `unknown persisted status fails closed to idle`() {
        assertEquals(CaptureUiStatus.IDLE, CaptureUiStatus.fromStoredValue("unexpected"))
        assertEquals(CaptureUiStatus.IDLE, CaptureUiStatus.fromStoredValue(null))
    }

    @Test
    fun `known persisted statuses round trip`() {
        CaptureUiStatus.entries.forEach { status ->
            assertEquals(status, CaptureUiStatus.fromStoredValue(status.name))
        }
    }
}