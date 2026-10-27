package com.collol.voicetranslation.service

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat

/** Internal gateway that requests microphone consent while A is visibly interacting with the app. */
class MicrophonePermissionActivity : ComponentActivity() {
    private val permissionRequest = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            CaptureUiStatusStore.write(this, CaptureUiStatus.STARTING)
            startCaptureService()
        } else {
            CaptureUiStatusStore.write(this, CaptureUiStatus.PERMISSION_DENIED)
        }
        finish()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (hasMicrophonePermission()) {
            CaptureUiStatusStore.write(this, CaptureUiStatus.STARTING)
            startCaptureService()
            finish()
        } else {
            permissionRequest.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    private fun hasMicrophonePermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    private fun startCaptureService() {
        ContextCompat.startForegroundService(
            this,
            Intent(this, MicrophoneCaptureService::class.java)
                .setAction(MicrophoneCaptureService.ACTION_START),
        )
    }
}

/** Explicit commands for the app-owned UI; no other application can invoke the service. */
object MicrophoneCaptureCommands {
    fun isServiceActive(): Boolean = MicrophoneCaptureService.active

    fun requestStart(activity: Activity) {
        activity.startActivity(Intent(activity, MicrophonePermissionActivity::class.java))
    }

    fun stop(context: Context) {
        context.stopService(Intent(context, MicrophoneCaptureService::class.java))
    }
}
