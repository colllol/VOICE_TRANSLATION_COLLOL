package com.collol.voicetranslation.desktop

import java.net.HttpURLConnection
import java.net.URI

class BackendClient(private val baseUrl: String = "http://127.0.0.1:8765") {
    fun health(): Boolean {
        return try {
            val connection = URI.create("$baseUrl/health").toURL().openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 1000
            connection.readTimeout = 1000
            try {
                connection.responseCode == 200
            } finally {
                connection.disconnect()
            }
        } catch (_: Exception) {
            false
        }
    }
}
