package com.collol.voicetranslation.desktop

import java.io.File

import java.util.concurrent.TimeUnit

class BackendSupervisor(
    private val processFactory: () -> Process,
    private val healthCheck: () -> Boolean,
    private val waitMillis: (Long) -> Unit = { Thread.sleep(it) },
    private val attempts: Int = 40,
) : AutoCloseable {
    private var child: Process? = null
    val ownsProcess: Boolean get() = child?.isAlive == true

    @Synchronized
    fun start() {
        if (healthCheck()) return
        val process = processFactory()
        child = process
        try {
            repeat(attempts) {
                if (healthCheck()) return
                check(process.isAlive) { "Backend process exited during startup. See backend.log." }
                waitMillis(250)
            }
            error("Backend did not become ready. See backend.log.")
        } catch (failure: Exception) {
            close()
            throw failure
        }
    }

    @Synchronized
    override fun close() {
        val process = child ?: return
        child = null
        try {
            process.outputStream.close()
            if (process.waitFor(5, TimeUnit.SECONDS)) return
        } finally {
            if (process.isAlive) process.destroyForcibly()
        }
    }

    companion object {
        fun packaged(backend: BackendClient): BackendSupervisor = BackendSupervisor(
            processFactory = {
                val executable = System.getProperty("compose.application.resources.dir")
                    ?.let(::File)?.resolve("backend/VoiceTranslationBackend/VoiceTranslationBackend.exe")
                    ?: error("Packaged backend executable was not found")
                check(executable.isFile) { "Packaged backend executable was not found" }
                val dataDir = System.getenv("LOCALAPPDATA")?.let(::File)?.resolve("VoiceTranslationComputer")
                    ?: File(System.getProperty("user.home"), ".voice-translation")
                check(dataDir.isDirectory || dataDir.mkdirs()) { "Could not create backend data folder" }
                ProcessBuilder(executable.absolutePath, "--desktop-child")
                    .directory(executable.parentFile)
                    .redirectErrorStream(true)
                    .redirectOutput(ProcessBuilder.Redirect.appendTo(dataDir.resolve("backend.log")))
                    .apply {
                        environment().putIfAbsent("VOICE_TRANSLATION_DB_PATH", dataDir.resolve("computer-data.db").absolutePath)
                        environment()["VOICE_TRANSLATION_PORT"] = backend.port.toString()
                    }
                    .start()
            },
            healthCheck = backend::health,
        )
    }
}
