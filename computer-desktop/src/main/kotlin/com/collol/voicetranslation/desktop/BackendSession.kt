package com.collol.voicetranslation.desktop

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.net.URI
import java.net.http.HttpClient
import java.net.http.WebSocket
import java.time.Duration
import java.util.Base64
import java.util.UUID
import java.util.concurrent.CompletionStage
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit

class BackendSession private constructor(
    val id: String,
    private val socket: WebSocket,
    private val listener: SessionListener,
    val supportsUtterances: Boolean,
    val provider: String,
) : AutoCloseable {
    val connected: Boolean get() = !socket.isInputClosed && !socket.isOutputClosed
    private val nextChunk = mutableMapOf<String, Int>()

    internal fun translateUtterance(stream: String, pcm: ByteArray): ByteArray {
        require(supportsUtterances && stream in setOf("a2b", "b2a"))
        require(pcm.size in 640..320_000 && pcm.size % 640 == 0)
        for (offset in pcm.indices step 640) {
            val sequence = nextChunk[stream] ?: 0
            val payload = JsonObject().apply {
                addProperty("stream_id", stream)
                addProperty("seq", sequence)
                addProperty("data_b64", Base64.getEncoder().encodeToString(pcm.copyOfRange(offset, offset + 640)))
            }
            val ack = exchange(socket, listener, "utterance.chunk", id, payload, "utterance.ack").getAsJsonObject("payload")
            check(ack.get("stream_id").asString == stream && ack.get("seq").asInt == sequence)
            nextChunk[stream] = sequence + 1
        }
        val payload = JsonObject().apply { addProperty("stream_id", stream) }
        val output = exchange(socket, listener, "utterance.finish", id, payload, "utterance.output", 60)
            .getAsJsonObject("payload")
        check(output.get("stream_id").asString == stream)
        return Base64.getDecoder().decode(output.get("data_b64").asString).also {
            check(it.size in 2..1_920_000 && it.size % 2 == 0) { "Invalid playback PCM" }
        }
    }

    fun cancel() {
        try {
            exchange(socket, listener, "session.cancel", id, JsonObject(), "session.cancelled")
        } finally {
            close()
        }
    }

    override fun close() = socket.abort()

    companion object {
        internal fun start(baseUrl: String, source: String, target: String): BackendSession {
            val listener = SessionListener()
            val uri = URI.create(baseUrl.replaceFirst("http", "ws") + "/ws")
            val http = HttpClient.newHttpClient()
            val connecting = http.newWebSocketBuilder().connectTimeout(Duration.ofSeconds(3))
                .buildAsync(uri, listener)
            val socket = try {
                connecting.get(4, TimeUnit.SECONDS)
            } catch (failure: Exception) {
                connecting.thenAccept { it.abort() }
                throw failure
            }
            try {
                val payload = JsonObject().apply {
                    addProperty("source_lang", source)
                    addProperty("target_lang", target)
                }
                val response = exchange(socket, listener, "session.start", null, payload, "session.started")
                val id = response.get("session_id").asString
                check(id.isNotBlank()) { "Backend returned an empty session ID" }
                val info = response.getAsJsonObject("payload")
                return BackendSession(id, socket, listener,
                    info.get("utterance_audio")?.asString == "chunks-v1", info.get("provider")?.asString ?: "unknown")
            } catch (failure: Exception) {
                socket.abort()
                throw failure
            }
        }
    }
}

private class SessionListener : WebSocket.Listener {
    private val text = StringBuilder()
    val messages = LinkedBlockingQueue<Result<String>>(8)

    override fun onOpen(webSocket: WebSocket) { webSocket.request(1) }

    override fun onText(webSocket: WebSocket, data: CharSequence, last: Boolean): CompletionStage<*>? {
        if (data.length > 2_565_000 - text.length) {
            onError(webSocket, IllegalStateException("Oversized WebSocket response"))
            webSocket.abort()
            return null
        }
        text.append(data)
        if (last && !messages.offer(Result.success(text.toString()))) {
            webSocket.abort()
            return null
        }
        if (last) text.clear()
        webSocket.request(1)
        return null
    }

    override fun onClose(webSocket: WebSocket, statusCode: Int, reason: String): CompletionStage<*>? {
        messages.offer(Result.failure(IllegalStateException("Backend closed the session ($statusCode)")))
        return null
    }

    override fun onError(webSocket: WebSocket, error: Throwable) {
        messages.offer(Result.failure(error))
    }
}

private fun exchange(
    socket: WebSocket, listener: SessionListener, type: String, sessionId: String?,
    payload: JsonObject, expected: String, timeoutSeconds: Long = 5,
): JsonObject {
    val requestId = UUID.randomUUID().toString()
    val request = JsonObject().apply {
        addProperty("v", 1)
        addProperty("type", type)
        addProperty("message_id", requestId)
        if (sessionId != null) addProperty("session_id", sessionId)
        add("payload", payload)
    }
    socket.sendText(request.toString(), true).get(3, TimeUnit.SECONDS)
    val text = listener.messages.poll(timeoutSeconds, TimeUnit.SECONDS)?.getOrThrow()
        ?: error("Backend did not answer")
    val response = JsonParser.parseString(text).asJsonObject
    if (response.get("type")?.asString == "error") {
        error(response.getAsJsonObject("payload")?.get("code")?.asString ?: "Backend rejected request")
    }
    check(response.get("v")?.asInt == 1 && response.get("message_id")?.asString == requestId &&
        response.get("type")?.asString == expected &&
        (sessionId == null || response.get("session_id")?.asString == sessionId)) {
        "Unexpected backend response"
    }
    return response
}
