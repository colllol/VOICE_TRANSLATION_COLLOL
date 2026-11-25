package com.collol.voicetranslation.desktop

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runInterruptible
import kotlinx.coroutines.withContext

fun main() {
    val port = System.getenv("VOICE_TRANSLATION_PORT")?.toIntOrNull()?.takeIf { it in 1..65535 } ?: 8765
    val backend = BackendClient("http://127.0.0.1:$port")
    BackendSupervisor.packaged(backend).use { supervisor -> runOperator(backend, supervisor) }
}

private fun runOperator(backend: BackendClient, backendSupervisor: BackendSupervisor) = application {
    var session by remember { mutableStateOf<BackendSession?>(null) }
    var backendReady by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(true) }
    var status by remember { mutableStateOf("Session stopped") }
    var settings by remember { mutableStateOf<LanguageSettings?>(null) }
    var voiceTest by remember { mutableStateOf<Job?>(null) }
    var speakerTest by remember { mutableStateOf<Job?>(null) }
    var traceLines by remember { mutableStateOf(listOf<String>()) }

    val scope = rememberCoroutineScope()

    fun trace(line: String) {
        val stamp = java.time.LocalTime.now().withNano(0).toString()
        traceLines = (traceLines + "$stamp  $line").takeLast(200)
    }
    fun dBfs(value: Double): String = String.format("%.1f dBFS", value)
    fun kBytes(bytes: Int): String = String.format("%.1f kB", bytes / 1024.0)

    fun testSpeaker() {
        if (speakerTest != null) return
        speakerTest = scope.launch {
            try {
                status = "Playing a 1 second test tone…"
                trace("speaker: requesting 1000 ms tone")
                val played = withContext(Dispatchers.IO) { LocalVoiceAudio.playTone(1_000) }
                trace("speaker: ${played.device} ${kBytes(played.bytes)} played ${played.playedMs} ms of ${played.expectedMs} ms")
                status = if (played.complete) {
                    "Speaker ok — ${played.playedMs} ms tone played on ${played.device}"
                } else {
                    "Speaker stopped early (${played.playedMs} of ${played.expectedMs} ms). Check the Windows output device."
                }
            } catch (_: TimeoutCancellationException) {
                trace("speaker: timed out")
                status = "Speaker test timed out. Check the Windows output device."
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                trace("speaker: failed — ${failure.message}")
                status = "Speaker test failed: ${failure.message ?: "no output device"}"
            } finally {
                speakerTest = null
            }
        }
    }
    fun testVoice(active: BackendSession, stream: String) {
        voiceTest = scope.launch {
            try {
                status = "Recording for 4 seconds… say something now"
                trace("mic: recording $stream for 4 s")
                val captured = withContext(Dispatchers.IO) { LocalVoiceAudio.record() }
                val info = captured.info
                trace(
                    "mic: ${info.device} ${kBytes(info.bytes)} ${info.durationMs} ms " +
                        "rms ${dBfs(info.rmsDbfs)} peak ${dBfs(info.peakDbfs)} " +
                        "silent ${(info.silentRatio * 100).toInt()}%"
                )
                if (info.silentRatio >= 0.95) {
                    trace("mic: recording is silent — nothing sent to the backend")
                    status = "Microphone captured silence. Check the Windows input device, its mute switch and microphone access for desktop apps."
                    return@launch
                }
                status = if (active.provider == "fake") "Checking local audio…" else "Translating with Azure…"
                val startedAt = System.nanoTime()
                val output = runInterruptible(Dispatchers.IO) { active.translateUtterance(stream, captured.pcm) }
                val translateMs = (System.nanoTime() - startedAt) / 1_000_000
                trace("backend: ${kBytes(output.size)} back in $translateMs ms (${active.provider})")
                status = "Playing output…"
                val played = withContext(Dispatchers.IO) { LocalVoiceAudio.play(output) }
                trace("speaker: ${kBytes(played.bytes)} played ${played.playedMs} ms of ${played.expectedMs} ms")
                status = if (active.provider == "fake") {
                    if (played.complete) {
                        "Round trip ok — mic ${dBfs(info.rmsDbfs)}, $translateMs ms backend, ${played.playedMs} ms tone (no translation)"
                    } else {
                        "Playback stopped early (${played.playedMs} of ${played.expectedMs} ms). Check the output device."
                    }
                } else if (played.complete) {
                    "Translated audio played — $translateMs ms backend round trip"
                } else {
                    "Playback stopped early (${played.playedMs} of ${played.expectedMs} ms). Check the output device."
                }
            } catch (_: TimeoutCancellationException) {
                active.close()
                session = null
                trace("voice test: timed out")
                status = "Audio device timed out. Check Windows audio settings and start a new session."
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                active.close()
                session = null
                trace("voice test: failed — ${failure.message}")
                status = "Voice test failed: ${failure.message ?: "check microphone and speaker"}. Start a new session."
            } finally {
                voiceTest = null
            }
        }
    }
    fun stop(exit: Boolean = false, disconnected: Boolean = false) {
        val active = session
        val test = voiceTest
        busy = true
        test?.cancel()
        if (test != null || disconnected) active?.close()
        scope.launch {
            test?.join()
            val result = if (test != null || disconnected) null else
                withContext(Dispatchers.IO) { runCatching { active?.cancel() } }
            session = null
            status = when {
                disconnected -> "Session disconnected"
                test != null -> "Voice test cancelled. Start a new session."
                result?.isSuccess == true -> "Session stopped"
                else -> "Connection closed. Stop was not confirmed."
            }
            if (disconnected) backendReady = false
            busy = false
            if (exit) exitApplication()
        }
    }
    LaunchedEffect(session) {
        val active = session ?: return@LaunchedEffect
        while (active.connected) delay(300)
        if (!busy && session === active) stop(disconnected = true)
    }
    suspend fun connectBackend() {
        status = "Connecting to backend…"
        val result = withContext(Dispatchers.IO) {
            runCatching {
                backendSupervisor.start()
                backend.loadSettings()
            }
        }
        settings = result.getOrNull()
        backendReady = result.isSuccess
        trace("backend: ${if (backendReady) "ready on port ${backend.port}" else "unavailable"}")
        status = if (backendReady) "Session stopped" else result.exceptionOrNull()?.message ?: "Backend unavailable"
        busy = false
    }
    LaunchedEffect(Unit) {
        trace("audio in:  ${LocalVoiceAudio.inputDevice()}")
        trace("audio out: ${LocalVoiceAudio.outputDevice()}")
        trace("format: 16000 Hz mono pcm_s16le, 20 ms frames (640 B)")
        connectBackend()
    }
    Window(onCloseRequest = {
        speakerTest?.cancel()
        if (!busy) stop(exit = true)
    }, title = "Voice Translation — Operator") {
        MaterialTheme {
            Column(
                modifier = Modifier.fillMaxSize().padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text("Voice Translation", style = MaterialTheme.typography.headlineMedium)
                Text(if (backendReady) "Backend: ready" else "Backend: unavailable")
                Button(enabled = !busy && session == null, onClick = {
                    busy = true
                    scope.launch { connectBackend() }
                }) {
                    Text("Check backend")
                }
                settings?.let { pair ->
                    Text("Languages: ${pair.source} → ${pair.target}")
                    Button(enabled = !busy && backendReady && session == null, onClick = {
                        busy = true
                        scope.launch {
                            val result = withContext(Dispatchers.IO) {
                                runCatching { backend.saveSettings(LanguageSettings(pair.target, pair.source)) }
                            }
                            result.getOrNull()?.let {
                                settings = it
                                trace("settings: ${it.source} → ${it.target}")
                            }
                            status = if (result.isSuccess) "Languages saved" else "Could not save languages"
                            busy = false
                        }
                    }) { Text("Swap and save languages") }
                }
                Text(status)
                Button(enabled = !busy && voiceTest == null && (backendReady || session != null), onClick = {
                    val pair = settings
                    if (session != null) stop() else if (pair != null) {
                        busy = true
                        status = "Starting session…"
                        scope.launch {
                            val result = withContext(Dispatchers.IO) { runCatching { backend.start(pair.source, pair.target) } }
                            session = result.getOrNull()
                            status = if (session == null) "Could not start session. Check the backend and retry."
                                else "Session active (${session?.id})"
                            trace("session: ${session?.id ?: "start failed"} · provider ${session?.provider ?: "unknown"}")
                            busy = false
                        }
                    }
                }) {
                    Text(if (session != null) "Stop session" else "Start session")
                }

                Text("Speaker self-test (no microphone, no session)", style = MaterialTheme.typography.titleSmall)
                Button(enabled = speakerTest == null, onClick = { testSpeaker() }) {
                    Text(if (speakerTest == null) "Test speaker: 1 s tone" else "Playing…")
                }

                session?.let { active ->
                    if (active.supportsUtterances) {
                        Text(if (active.provider == "fake") "Local test tone (offline)" else "Local voice test: ${active.provider}")
                        val pair = settings
                        val supportedPair = active.provider == "fake" ||
                            (active.provider == "azure" && pair != null && setOf(pair.source, pair.target) == setOf("vi", "en"))
                        if (active.provider == "azure") {
                            Text("Testing sends your microphone audio and recognized text to Azure. Vietnamese and English only.")
                        }
                        if (voiceTest == null && pair != null && supportedPair) {
                            Button(enabled = !busy, onClick = { testVoice(active, "a2b") }) { Text("Test mic: ${pair.source} → ${pair.target}") }
                            Button(enabled = !busy, onClick = { testVoice(active, "b2a") }) { Text("Test mic: ${pair.target} → ${pair.source}") }
                        } else if (voiceTest != null) {
                            Button(enabled = !busy, onClick = { stop() }) { Text("Cancel voice test") }
                        }
                    } else {
                        Text("Local voice test unavailable: backend update required")
                    }
                }

                Text("Audio pipeline", style = MaterialTheme.typography.titleSmall)
                Text(
                    if (traceLines.isEmpty()) "waiting for the first measurement…" else traceLines.joinToString("\n"),
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.fillMaxWidth().heightIn(max = 260.dp)
                        .verticalScroll(rememberScrollState()),
                )
            }
        }
    }
}