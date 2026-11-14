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

fun main() = application {
    var running by remember { mutableStateOf(false) }
    var backendReady by remember { mutableStateOf(false) }
    val backend = remember { BackendClient() }
    Window(onCloseRequest = ::exitApplication, title = "Voice Translation — Operator") {
        MaterialTheme {
            Column(
                modifier = Modifier.fillMaxSize().padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text("Voice Translation", style = MaterialTheme.typography.headlineMedium)
                Text(if (backendReady) "Backend: ready" else "Backend: unavailable")
                Button(onClick = { backendReady = backend.health() }) {
                    Text("Check backend")
                }
                Text(if (running) "Session: active" else "Session: stopped")
                Button(onClick = { if (backendReady) running = !running }) {
                    Text(if (running) "Stop session" else "Start session")
                }
                Text("Controlled A-side operator console. VoIP media integration is not enabled in this slice.")
            }
        }
    }
}
