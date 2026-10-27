package com.collol.voicetranslation.developer

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.collol.voicetranslation.audio.AudioDiagnosticsRecorder
import com.collol.voicetranslation.audio.AudioMetrics
import com.collol.voicetranslation.service.MicrophoneCaptureCommands
import com.google.mlkit.common.model.DownloadConditions
import com.google.mlkit.nl.translate.Translation
import com.google.mlkit.nl.translate.Translator
import com.google.mlkit.nl.translate.TranslatorOptions
import java.util.Locale
import kotlin.math.roundToInt

/** One-way developer harness: speak on A, translate locally, and play the result. */
class DeveloperVoiceLabActivity : ComponentActivity() {
    private var running by mutableStateOf(false)
    private var isListening by mutableStateOf(false)
    private var status by mutableStateOf("Sẵn sàng")
    private var transcript by mutableStateOf("")
    private var translation by mutableStateOf("")
    private var metrics by mutableStateOf(AudioMetrics(0.0, 0.0, 0))
    private var chunkCount by mutableStateOf(0)
    private val events = mutableStateListOf<String>()
    private var speechRecognizer: SpeechRecognizer? = null
    private var translator: Translator? = null
    private var textToSpeech: TextToSpeech? = null
    private var diagnostics: AudioDiagnosticsRecorder? = null
    private var stageStartedAtMillis = 0L
    private var asrClientRetryCount = 0
    private var runGeneration = 0L
    private var utteranceGeneration = 0L
    private var diagnosticsReleasePending = false
    private var deferredStartRequested = false

    private val permissionRequest = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) startLab() else setError("Cần cấp quyền microphone để chạy Voice Lab")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        textToSpeech = TextToSpeech(this) { result ->
            if (result == TextToSpeech.SUCCESS) log("TTS sẵn sàng")
            else setError("TTS không khởi tạo được")
        }
        setContent { MaterialTheme { VoiceLabScreen() } }
    }

    override fun onDestroy() {
        stopLab()
        translator?.close()
        textToSpeech?.shutdown()
        super.onDestroy()
    }

    private fun toggleLab() {
        if (running) stopLab()
        else if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startLab()
        } else {
            permissionRequest.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    private fun startLab() {
        if (diagnosticsReleasePending) {
            deferredStartRequested = true
            status = "Đang giải phóng microphone trước khi bắt đầu lại..."
            return
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            setError("Thiết bị không có SpeechRecognizer khả dụng")
            return
        }
        clearRun()
        val generation = ++runGeneration
        MicrophoneCaptureCommands.stop(this)
        running = true
        stageStartedAtMillis = SystemClock.elapsedRealtime()
        status = "Đang chuẩn bị model dịch..."
        log("Bắt đầu developer one-way voice test")
        diagnostics = AudioDiagnosticsRecorder(
            onMetrics = { value ->
                runOnUiThread {
                    if (isCurrentRun(generation)) {
                        metrics = value
                        chunkCount++
                    }
                }
            },
            onFailure = { cause ->
                runOnUiThread {
                    if (isCurrentRun(generation)) log("Audio metrics lỗi: ${cause.message}")
                }
            },
        ).also { it.start() }
        translator = Translation.getClient(
            TranslatorOptions.Builder()
                .setSourceLanguage(SOURCE_LANGUAGE)
                .setTargetLanguage(TARGET_LANGUAGE)
                .build(),
        )
        translator?.downloadModelIfNeeded(DownloadConditions.Builder().build())
            ?.addOnSuccessListener {
                if (!isCurrentRun(generation)) return@addOnSuccessListener
                log("Model dịch $SOURCE_LANGUAGE->$TARGET_LANGUAGE sẵn sàng trong ${elapsedStageMillis()} ms")
                status = "Đang nghe... Hãy nói một câu"
                startRecognition(generation, ++utteranceGeneration)
            }
            ?.addOnFailureListener { cause ->
                if (isCurrentRun(generation)) setError("Không tải được model dịch: ${cause.message}")
            }
    }

    private fun startRecognition(generation: Long, utterance: Long) {
        if (!isCurrentUtterance(generation, utterance)) return
        textToSpeech?.stop()
        val recorder = diagnostics
        if (recorder == null) {
            window.decorView.postDelayed({
                if (isCurrentUtterance(generation, utterance)) createSpeechRecognizer(generation, utterance)
            }, MICROPHONE_RELEASE_DELAY_MILLIS)
        } else {
            diagnostics = null
            diagnosticsReleasePending = true
            recorder.stop {
                window.decorView.post {
                    diagnosticsReleasePending = false
                    if (isCurrentUtterance(generation, utterance)) {
                        log("Audio diagnostics đã release trước ASR")
                        createSpeechRecognizer(generation, utterance)
                    } else {
                        startDeferredRunIfRequested()
                    }
                }
            }
        }
    }

    private fun createSpeechRecognizer(generation: Long, utterance: Long) {
        if (!isCurrentUtterance(generation, utterance)) return
        stageStartedAtMillis = SystemClock.elapsedRealtime()
        speechRecognizer?.destroy()
        speechRecognizer = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && SpeechRecognizer.isOnDeviceRecognitionAvailable(this)) {
            log("ASR: on-device")
            SpeechRecognizer.createOnDeviceSpeechRecognizer(this)
        } else {
            log("ASR: system recognizer")
            SpeechRecognizer.createSpeechRecognizer(this)
        }.also { recognizer ->
            recognizer.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {
                    if (isCurrentUtterance(generation, utterance)) status = "Đang nghe..."
                }
                override fun onBeginningOfSpeech() {
                    if (isCurrentUtterance(generation, utterance)) { isListening = true; status = "Đang nhận giọng nói..." }
                }
                override fun onRmsChanged(rmsdB: Float) {
                    if (isCurrentUtterance(generation, utterance) && rmsdB.isFinite()) {
                        metrics = metrics.copy(rms = VoiceLabAudioPolicy.normalizedRmsFromSpeechDb(rmsdB))
                        logThrottled("ASR RMS ${rmsdB.roundToInt()} dB")
                    }
                }
                override fun onEndOfSpeech() {
                    if (isCurrentUtterance(generation, utterance)) { isListening = false; status = "Đang xử lý ASR..." }
                }
                override fun onResults(results: Bundle?) {
                    if (!isCurrentUtterance(generation, utterance)) return
                    asrClientRetryCount = 0
                    val value = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                    if (value.isBlank()) {
                        setError("ASR không trả transcript")
                    } else {
                        transcript = value
                        log("ASR hoàn tất trong ${elapsedStageMillis()} ms: ${value.take(80)}")
                        translate(value, generation, utterance)
                    }
                }
                override fun onError(error: Int) {
                    if (!isCurrentUtterance(generation, utterance)) return
                    isListening = false
                    if (running && error == SpeechRecognizer.ERROR_CLIENT && asrClientRetryCount == 0) {
                        asrClientRetryCount++
                        log("ASR client lỗi mã 5; giải phóng recognizer và thử lại một lần")
                        speechRecognizer?.destroy()
                        speechRecognizer = null
                        window.decorView.postDelayed({
                            if (isCurrentUtterance(generation, utterance)) {
                                startRecognition(generation, utterance)
                            }
                        }, ASR_RETRY_DELAY_MILLIS)
                    } else if (running) {
                        setError("ASR lỗi mã $error")
                    }
                }
                override fun onBufferReceived(buffer: ByteArray?) = Unit
                override fun onPartialResults(partialResults: Bundle?) = Unit
                override fun onEvent(eventType: Int, params: Bundle?) = Unit
                override fun onSegmentResults(segmentResults: Bundle) = Unit
            })
        }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, SOURCE_LOCALE.toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        runCatching { speechRecognizer?.startListening(intent) }
            .onFailure { setError("Không thể khởi động ASR: ${it.message}") }
    }

    private fun translate(value: String, generation: Long, utterance: Long) {
        if (!isCurrentUtterance(generation, utterance)) return
        status = "Đang dịch..."
        stageStartedAtMillis = SystemClock.elapsedRealtime()
        translator?.translate(value)
            ?.addOnSuccessListener { result ->
                if (!isCurrentUtterance(generation, utterance)) return@addOnSuccessListener
                translation = result
                log("NMT hoàn tất trong ${elapsedStageMillis()} ms: ${result.take(80)}")
                status = "Đang phát TTS..."
                val tts = textToSpeech
                val languageResult = tts?.setLanguage(TARGET_LOCALE)
                if (tts == null || languageResult == TextToSpeech.LANG_MISSING_DATA || languageResult == TextToSpeech.LANG_NOT_SUPPORTED) {
                    setError("TTS không hỗ trợ ngôn ngữ đích trên thiết bị")
                    return@addOnSuccessListener
                }
                stageStartedAtMillis = SystemClock.elapsedRealtime()
                val utteranceId = "developer-${SystemClock.elapsedRealtime()}"
                tts.setOnUtteranceProgressListener(object : android.speech.tts.UtteranceProgressListener() {
                    override fun onStart(id: String?) = Unit
                    override fun onDone(id: String?) {
                        if (id == utteranceId && isCurrentUtterance(generation, utterance)) runOnUiThread {
                            if (isCurrentUtterance(generation, utterance)) {
                                log("TTS phát xong trong ${elapsedStageMillis()} ms")
                                status = "Hoàn tất; bấm Nói câu khác để chạy tiếp"
                            }
                        }
                    }
                    @Deprecated("Deprecated in Java")
                    override fun onError(id: String?) {
                        if (id == utteranceId && isCurrentUtterance(generation, utterance)) runOnUiThread {
                            if (isCurrentUtterance(generation, utterance)) setError("TTS không phát được kết quả")
                        }
                    }
                })
                if (tts.speak(result, TextToSpeech.QUEUE_FLUSH, null, utteranceId) == TextToSpeech.ERROR) {
                    setError("Không thể đưa kết quả vào TTS")
                } else {
                    log("TTS bắt đầu phát ra loa")
                }
            }
            ?.addOnFailureListener { cause ->
                if (isCurrentUtterance(generation, utterance)) setError("Dịch lỗi: ${cause.message}")
            }
    }

    private fun startNextUtterance() {
        if (!running || diagnosticsReleasePending) return
        transcript = ""
        translation = ""
        isListening = false
        status = "Đang chuẩn bị microphone..."
        startRecognition(runGeneration, ++utteranceGeneration)
    }

    private fun stopLab() {
        if (!running && diagnostics == null) return
        runGeneration++
        running = false
        isListening = false
        speechRecognizer?.cancel()
        speechRecognizer?.destroy()
        speechRecognizer = null
        textToSpeech?.stop()
        diagnostics?.let { recorder ->
            diagnosticsReleasePending = true
            recorder.stop {
                window.decorView.post {
                    diagnosticsReleasePending = false
                    startDeferredRunIfRequested()
                }
            }
        }
        diagnostics = null
        translator?.close()
        translator = null
        status = "Đã dừng"
        log("Đã dừng developer voice test; audio không được lưu")
    }

    private fun clearRun() {
        events.clear()
        transcript = ""
        translation = ""
        chunkCount = 0
        metrics = AudioMetrics(0.0, 0.0, 0)
        asrClientRetryCount = 0
    }

    private fun isCurrentRun(generation: Long): Boolean =
        VoiceLabAudioPolicy.isCurrentRun(generation, runGeneration, running)

    private fun isCurrentUtterance(generation: Long, utterance: Long): Boolean =
        isCurrentRun(generation) && VoiceLabAudioPolicy.isCurrentUtterance(utterance, utteranceGeneration)

    private fun startDeferredRunIfRequested() {
        if (deferredStartRequested && !isFinishing) {
            deferredStartRequested = false
            startLab()
        }
    }

    private fun setError(message: String) {
        log("ERROR: $message")
        stopLab()
        status = message
    }

    private fun elapsedStageMillis(): Long = SystemClock.elapsedRealtime() - stageStartedAtMillis

    private var lastRmsLogMillis = 0L
    private fun logThrottled(message: String) {
        val now = System.currentTimeMillis()
        if (now - lastRmsLogMillis >= 1000L) {
            lastRmsLogMillis = now
            log(message)
        }
    }

    private fun log(message: String) {
        runOnUiThread {
            events.add("${events.size + 1}. $message")
            if (events.size > 30) events.removeAt(0)
        }
    }

    @Composable
    private fun VoiceLabScreen() {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text("Developer Voice Lab", style = MaterialTheme.typography.headlineMedium)
            Text("One-way test: A nói vào microphone, ASR -> dịch on-device -> TTS phát ra loa.")
            Text("Chỉ thu giọng nói trực tiếp từ microphone, không thu/chèn audio cuộc gọi. PCM không lưu. Dùng on-device ASR nếu có; system recognizer có thể xử lý audio qua dịch vụ bên ngoài. Transcript chỉ hiện trong màn hình test.", style = MaterialTheme.typography.bodySmall)
            Text("Trạng thái: $status")
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = ::toggleLab) { Text(if (running) "Dừng test" else "Bắt đầu test") }
                if (running && !isListening && transcript.isNotBlank() && translation.isNotBlank() && status.startsWith("Hoàn tất")) {
                    OutlinedButton(onClick = ::startNextUtterance) { Text("Nói câu khác") }
                }
                OutlinedButton(onClick = { finish() }) { Text("Đóng") }
            }
            HorizontalDivider()
            Text("Audio diagnostics", style = MaterialTheme.typography.titleMedium)
            Text("Sample rate: ${AudioDiagnosticsRecorder.SAMPLE_RATE_HZ} Hz")
            Text("RMS: ${"%.3f".format(Locale.US, metrics.rms)}   Peak: ${"%.3f".format(Locale.US, metrics.peak)}")
            Text("Dominant frequency: ${metrics.dominantFrequencyHz} Hz   Windows: $chunkCount")
            Text("ASR: ${if (transcript.isBlank()) "chưa có kết quả" else transcript}")
            Text("Translated: ${if (translation.isBlank()) "chưa có kết quả" else translation}")
            HorizontalDivider()
            Text("Processing trace", style = MaterialTheme.typography.titleMedium)
            events.forEach { event -> Text(event, style = MaterialTheme.typography.bodySmall) }
        }
    }

    companion object {
        private const val SOURCE_LANGUAGE = "vi"
        private const val TARGET_LANGUAGE = "en"
        private val SOURCE_LOCALE = Locale.forLanguageTag("vi-VN")
        private val TARGET_LOCALE = Locale.US
        private const val ASR_RETRY_DELAY_MILLIS = 250L
        private const val MICROPHONE_RELEASE_DELAY_MILLIS = 350L
    }
}
