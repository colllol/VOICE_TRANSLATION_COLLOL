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
    Window(onCloseRequest = ::exitApplication, title = "Voice Translation — Operator") {
        MaterialTheme {
            Column(
                modifier = Modifier.fillMaxSize().padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text("Voice Translation", style = MaterialTheme.typography.headlineMedium)
                Text(if (running) "Backend session: active" else "Backend session: stopped")
                Button(onClick = { running = !running }) {
                    Text(if (running) "Stop session" else "Start session")
                }
                Text("Controlled A-side operator console. VoIP media integration is not enabled in this slice.")
            }
        }
    }
}
