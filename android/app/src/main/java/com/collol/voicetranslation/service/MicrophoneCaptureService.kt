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
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopCapture()
            stopSelfResult(startId)
            return START_NOT_STICKY
        }
        if (intent?.action != ACTION_START) {
            stopSelfResult(startId)
            return START_NOT_STICKY
        }
        if (!hasMicrophonePermission()) {
            stopSelfResult(startId)
            return START_NOT_STICKY
        }

        try {
            startForeground(NOTIFICATION_ID, buildNotification())
            if (captureController == null) {
                val capture = AudioRecordCapture.create(
                    chunkSink = PcmChunkSink { chunk -> onPcmChunk(chunk) },
                )
                captureController = CaptureLifecycleController(
                    permissionGate = MicrophonePermissionGate(::hasMicrophonePermission),
                    captureResource = capture,
                )
            }
            when (captureController?.start()) {
                is CaptureStartResult.Started -> Unit
                else -> stopCapture()
            }
        } catch (_: SecurityException) {
            stopCapture()
        } catch (_: RuntimeException) {
            stopCapture()
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        stopCapture()
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
        // The chunk remains in-process until a separately controlled transport is integrated.
        chunk.pcm.fill(0)
    }

    private fun buildNotification(): Notification =
        NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle("Voice Translation microphone")
            .setContentText("Capturing microphone audio on this device")
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
        private const val NOTIFICATION_CHANNEL_ID = "microphone_capture"
        private const val NOTIFICATION_ID = 1101
    }
}
