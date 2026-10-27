package com.collol.voicetranslation.service

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.collol.voicetranslation.R
import com.collol.voicetranslation.audio.AudioRecordCapture
import com.collol.voicetranslation.audio.CapturedPcmChunk
import com.collol.voicetranslation.audio.PcmChunkSink

/** A-owned microphone capture service; it does not intercept other applications' audio. */
class MicrophoneCaptureService : Service() {
    private var captureController: CaptureLifecycleController? = null

    override fun onCreate() {
        super.onCreate()
        active = true
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopCapture()
            CaptureUiStatusStore.write(this, CaptureUiStatus.IDLE)
            stopSelfResult(startId)
            return START_NOT_STICKY
        }
        if (intent?.action != ACTION_START) {
            stopSelfResult(startId)
            return START_NOT_STICKY
        }
        if (!hasMicrophonePermission()) {
            CaptureUiStatusStore.write(this, CaptureUiStatus.PERMISSION_DENIED)
            stopSelfResult(startId)
            return START_NOT_STICKY
        }

        try {
            CaptureUiStatusStore.write(this, CaptureUiStatus.STARTING)
            startForeground(NOTIFICATION_ID, buildNotification())
            if (captureController == null) {
                val capture = AudioRecordCapture.create(
                    chunkSink = PcmChunkSink { chunk -> onPcmChunk(chunk) },
                    onCaptureTerminated = {
                        CaptureUiStatusStore.write(this, CaptureUiStatus.IDLE)
                        stopCapture()
                        stopSelf()
                    },
                )
                captureController = CaptureLifecycleController(
                    permissionGate = MicrophonePermissionGate(::hasMicrophonePermission),
                    captureResource = capture,
                )
            }
            when (captureController?.start()) {
                is CaptureStartResult.Started ->
                    CaptureUiStatusStore.write(this, CaptureUiStatus.CAPTURING)
                CaptureStartResult.PermissionDenied -> {
                    stopCapture()
                    CaptureUiStatusStore.write(this, CaptureUiStatus.PERMISSION_DENIED)
                    stopSelfResult(startId)
                }
                else -> {
                    stopCapture()
                    CaptureUiStatusStore.write(this, CaptureUiStatus.FAILED)
                    stopSelfResult(startId)
                }
            }
        } catch (_: SecurityException) {
            stopCapture()
            CaptureUiStatusStore.write(this, CaptureUiStatus.PERMISSION_DENIED)
            stopSelfResult(startId)
        } catch (_: RuntimeException) {
            stopCapture()
            CaptureUiStatusStore.write(this, CaptureUiStatus.FAILED)
            stopSelfResult(startId)
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        active = false
        stopCapture()
        if (CaptureUiStatusStore.read(this) == CaptureUiStatus.CAPTURING ||
            CaptureUiStatusStore.read(this) == CaptureUiStatus.STARTING
        ) {
            CaptureUiStatusStore.write(this, CaptureUiStatus.IDLE)
        }
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun stopCapture() {
        captureController?.stopAndRelease()
        captureController = null
        stopForeground(STOP_FOREGROUND_REMOVE)
    }

    private fun hasMicrophonePermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    private fun onPcmChunk(chunk: CapturedPcmChunk) {
        if (!hasMicrophonePermission()) {
            stopCapture()
            return
        }
        // Keep the capture boundary in-process until a controlled transport is integrated.
        @Suppress("UNUSED_VARIABLE")
        val inProcessChunk = chunk
    }

    private fun buildNotification(): Notification =
        NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle("Voice Translation microphone")
            .setContentText("Capturing this device's microphone only; no call audio")
            .addAction(
                android.R.drawable.ic_media_pause,
                "Stop microphone",
                android.app.PendingIntent.getService(
                    this,
                    0,
                    Intent(this, MicrophoneCaptureService::class.java).setAction(ACTION_STOP),
                    android.app.PendingIntent.FLAG_UPDATE_CURRENT or android.app.PendingIntent.FLAG_IMMUTABLE,
                ),
            )
            .setOngoing(true)
            .build()

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "Microphone capture",
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
    }

    companion object {
        const val ACTION_START = "com.collol.voicetranslation.action.START_CAPTURE"
        const val ACTION_STOP = "com.collol.voicetranslation.action.STOP_CAPTURE"
        @Volatile
        var active: Boolean = false
            private set
        private const val NOTIFICATION_CHANNEL_ID = "microphone_capture"
        private const val NOTIFICATION_ID = 1101
    }
}
