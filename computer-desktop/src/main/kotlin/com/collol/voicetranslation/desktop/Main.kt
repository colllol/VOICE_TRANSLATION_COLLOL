package com.collol.voicetranslation.desktop

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
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

    val scope = rememberCoroutineScope()

    fun testVoice(active: BackendSession, stream: String) {
        voiceTest = scope.launch {
            try {
                status = "Recording for 4 seconds…"
                val pcm = withContext(Dispatchers.IO) { LocalVoiceAudio.record() }
                status = if (active.provider == "fake") "Checking local audio…" else "Translating with Azure…"
                val output = runInterruptible(Dispatchers.IO) { active.translateUtterance(stream, pcm) }
                status = "Playing output…"
                withContext(Dispatchers.IO) { LocalVoiceAudio.play(output) }
                status = if (active.provider == "fake") "Test tone played; no translation" else "Translated audio played"
            } catch (_: TimeoutCancellationException) {
                active.close()
                session = null
                status = "Audio device timed out. Check Windows audio settings and start a new session."
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                active.close()
                session = null
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
        status = if (backendReady) "Session stopped" else result.exceptionOrNull()?.message ?: "Backend unavailable"
        busy = false
    }
    LaunchedEffect(Unit) { connectBackend() }
    Window(onCloseRequest = {
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
                            result.getOrNull()?.let { settings = it }
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
                            busy = false
                        }
                    }
                }) {
                    Text(if (session != null) "Stop session" else "Start session")
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
            }
        }
    }
}
