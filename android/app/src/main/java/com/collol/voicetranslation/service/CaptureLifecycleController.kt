package com.collol.voicetranslation.service

interface CaptureResource {
    fun start()
    fun stop()
    fun release()
}

fun interface MicrophonePermissionGate {
    fun isGranted(): Boolean
}

enum class CaptureLifecycleState {
    IDLE,
    CAPTURING,
    RELEASED,
}

sealed interface CaptureStartResult {
    data object Started : CaptureStartResult
    data object PermissionDenied : CaptureStartResult
    data object AlreadyReleased : CaptureStartResult
    data class Failed(val cause: Throwable) : CaptureStartResult
}

/** Owns the terminal lifecycle so every started resource is stopped and released. */
class CaptureLifecycleController(
    private val permissionGate: MicrophonePermissionGate,
    private val captureResource: CaptureResource,
) {
    var state: CaptureLifecycleState = CaptureLifecycleState.IDLE
        private set

    fun start(): CaptureStartResult {
        when {
            state == CaptureLifecycleState.RELEASED -> return CaptureStartResult.AlreadyReleased
            state == CaptureLifecycleState.CAPTURING -> return CaptureStartResult.Started
            !permissionGate.isGranted() -> return CaptureStartResult.PermissionDenied
        }

        return try {
            captureResource.start()
            state = CaptureLifecycleState.CAPTURING
            CaptureStartResult.Started
        } catch (cause: Throwable) {
            stopAndRelease()
            CaptureStartResult.Failed(cause)
        }
    }

    fun stopAndRelease() {
        if (state == CaptureLifecycleState.RELEASED) return
        runCatching { captureResource.stop() }
        runCatching { captureResource.release() }
        state = CaptureLifecycleState.RELEASED
    }
}
