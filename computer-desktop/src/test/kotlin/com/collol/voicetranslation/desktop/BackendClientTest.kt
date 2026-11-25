package com.collol.voicetranslation.desktop

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFails
import java.util.concurrent.TimeUnit

class BackendClientTest {
    @Test
    fun healthIsFalseWhenBackendIsUnavailable() {
        assertFalse(BackendClient("http://127.0.0.1:1").health())
    }

    @Test
    fun existingBackendIsReusedAndNeverStoppedByThisApp() {
        var launches = 0
        val supervisor = BackendSupervisor(
            processFactory = { launches++; error("should not launch") },
            healthCheck = { true },
            waitMillis = {},
        )

        supervisor.start()
        supervisor.close()

        assertEquals(0, launches)
    }

    @Test
    fun packagedBackendStartsAndOnlyOwnedProcessIsStopped() {
        val process = FakeProcess()
        var ready = false
        val supervisor = BackendSupervisor(
            processFactory = { process },
            healthCheck = { ready },
            waitMillis = { ready = true },
        )

        supervisor.start()
        assertTrue(supervisor.ownsProcess)
        supervisor.close()

        assertTrue(process.destroyed)
    }

    @Test
    fun startupFailureDestroysChildAndReportsBackendUnavailable() {
        val process = FakeProcess()
        val supervisor = BackendSupervisor(
            processFactory = { process },
            healthCheck = { false },
            waitMillis = {},
            attempts = 2,
        )

        assertFails { supervisor.start() }
        assertTrue(process.destroyed)
        assertFalse(supervisor.ownsProcess)
    }
}

private class FakeProcess : Process() {
    var destroyed = false
    override fun getOutputStream() = java.io.ByteArrayOutputStream()
    override fun getInputStream() = java.io.ByteArrayInputStream(byteArrayOf())
    override fun getErrorStream() = java.io.ByteArrayInputStream(byteArrayOf())
    override fun waitFor(): Int = 0
    override fun waitFor(timeout: Long, unit: TimeUnit): Boolean = destroyed
    override fun exitValue(): Int = if (destroyed) 0 else throw IllegalThreadStateException()
    override fun destroy() { destroyed = true }
    override fun destroyForcibly(): Process { destroyed = true; return this }
    override fun isAlive(): Boolean = !destroyed
}
