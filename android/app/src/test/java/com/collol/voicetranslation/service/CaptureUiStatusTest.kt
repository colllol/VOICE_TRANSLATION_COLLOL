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

    @Test
    fun `permission revocation stops capture marks denial and stops service`() {
        val events = mutableListOf<String>()

        CapturePermissionRevocationHandler(
            stopCapture = { events += "capture-stopped" },
            markPermissionDenied = { events += "permission-denied" },
            stopService = { events += "service-stopped" },
        ).handle()

        assertEquals(
            listOf("capture-stopped", "permission-denied", "service-stopped"),
            events,
        )
    }
}