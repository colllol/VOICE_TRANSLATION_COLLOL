package com.collol.voicetranslation.service

import android.content.Context

enum class CaptureUiStatus {
    IDLE,
    STARTING,
    CAPTURING,
    PERMISSION_DENIED,
    FAILED;

    companion object {
        fun fromStoredValue(value: String?): CaptureUiStatus =
            entries.firstOrNull { it.name == value } ?: IDLE
    }
}

object CaptureUiStatusStore {
    private const val PREFERENCES = "microphone_capture"
    private const val STATUS = "status"

    fun read(context: Context): CaptureUiStatus =
        CaptureUiStatus.fromStoredValue(
            context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).getString(STATUS, null),
        )

    fun write(context: Context, status: CaptureUiStatus) {
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            .edit()
            .putString(STATUS, status.name)
            .apply()
    }
}

/** Keeps permission revocation cleanup ordered and independently testable. */
class CapturePermissionRevocationHandler(
    private val stopCapture: () -> Unit,
    private val markPermissionDenied: () -> Unit,
    private val stopService: () -> Unit,
) {
    fun handle() {
        stopCapture()
        markPermissionDenied()
        stopService()
    }
}