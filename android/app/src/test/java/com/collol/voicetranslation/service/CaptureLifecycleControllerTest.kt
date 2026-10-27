package com.collol.voicetranslation.service

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CaptureLifecycleControllerTest {
    @Test
    fun `permission denial fails closed without touching capture resource`() {
        val resource = RecordingCaptureResource()
        val controller = CaptureLifecycleController(
            permissionGate = MicrophonePermissionGate { false },
            captureResource = resource,
        )

        val result = controller.start()

        assertEquals(CaptureStartResult.PermissionDenied, result)
        assertEquals(CaptureLifecycleState.IDLE, controller.state)
        assertFalse(resource.started)
        assertFalse(resource.released)
    }

    @Test
    fun `successful start enters capturing and stop releases once`() {
        val resource = RecordingCaptureResource()
        val controller = CaptureLifecycleController(
            permissionGate = MicrophonePermissionGate { true },
            captureResource = resource,
        )

        assertEquals(CaptureStartResult.Started, controller.start())
        assertEquals(CaptureLifecycleState.CAPTURING, controller.state)

        controller.stopAndRelease()
        controller.stopAndRelease()

        assertEquals(CaptureLifecycleState.RELEASED, controller.state)
        assertEquals(1, resource.stopCalls)
        assertEquals(1, resource.releaseCalls)
    }

    @Test
    fun `start failure stops and releases partial resource`() {
        val resource = RecordingCaptureResource(failOnStart = true)
        val controller = CaptureLifecycleController(
            permissionGate = MicrophonePermissionGate { true },
            captureResource = resource,
        )

        val result = controller.start()

        assertTrue(result is CaptureStartResult.Failed)
        assertEquals(CaptureLifecycleState.RELEASED, controller.state)
        assertEquals(1, resource.stopCalls)
        assertEquals(1, resource.releaseCalls)
    }

    @Test
    fun `released controller cannot restart`() {
        val resource = RecordingCaptureResource()
        val controller = CaptureLifecycleController(
            permissionGate = MicrophonePermissionGate { true },
            captureResource = resource,
        )
        controller.stopAndRelease()

        val result = controller.start()

        assertEquals(CaptureStartResult.AlreadyReleased, result)
        assertEquals(0, resource.startCalls)
    }

    private class RecordingCaptureResource(
        private val failOnStart: Boolean = false,
    ) : CaptureResource {
        var started = false
        var released = false
        var startCalls = 0
        var stopCalls = 0
        var releaseCalls = 0

        override fun start() {
            startCalls++
            started = true
            if (failOnStart) error("start failed")
        }

        override fun stop() {
            stopCalls++
            started = false
        }

        override fun release() {
            releaseCalls++
            released = true
        }
    }
}
