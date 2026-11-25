package com.collol.voicetranslation.desktop

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.net.HttpURLConnection
import java.net.URI

data class LanguageSettings(val source: String, val target: String)

class BackendClient(private val baseUrl: String = "http://127.0.0.1:8765") {
    val port: Int get() = URI.create(baseUrl).port
    fun start(source: String, target: String): BackendSession = BackendSession.start(baseUrl, source, target)

    fun loadSettings(): LanguageSettings = settingsRequest(null)

    fun saveSettings(settings: LanguageSettings): LanguageSettings = settingsRequest(settings)

    private fun settingsRequest(settings: LanguageSettings?): LanguageSettings {
        val connection = URI.create("$baseUrl/settings").toURL().openConnection() as HttpURLConnection
        connection.connectTimeout = 2000
        connection.readTimeout = 3000
        connection.instanceFollowRedirects = false
        try {
            if (settings != null) {
                connection.requestMethod = "PUT"
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                val json = JsonObject().apply {
                    addProperty("source_lang", settings.source)
                    addProperty("target_lang", settings.target)
                }
                connection.outputStream.use { it.write(json.toString().toByteArray(Charsets.UTF_8)) }
            }
            check(connection.responseCode == 200) { "Backend settings request failed (${connection.responseCode})" }
            return connection.inputStream.bufferedReader(Charsets.UTF_8).use {
                val json = JsonParser.parseReader(it).asJsonObject
                LanguageSettings(json.get("source_lang").asString, json.get("target_lang").asString)
            }
        } finally {
            connection.disconnect()
        }
    }

    fun health(): Boolean {
        return try {
            val connection = URI.create("$baseUrl/health").toURL().openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 1000
            connection.readTimeout = 1000
            connection.instanceFollowRedirects = false
            try {
                connection.responseCode == 200 && connection.inputStream.bufferedReader(Charsets.UTF_8).use {
                    val health = JsonParser.parseReader(it).asJsonObject
                    health.get("status")?.asString == "ok" &&
                        health.get("service")?.asString == "voice-translation-computer"
                }
            } finally {
                connection.disconnect()
            }
        } catch (_: Exception) {
            false
        }
    }
}
