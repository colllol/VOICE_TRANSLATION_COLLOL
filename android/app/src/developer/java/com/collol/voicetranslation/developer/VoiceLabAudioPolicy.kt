package com.collol.voicetranslation.developer

import kotlin.math.pow

/** Keeps delayed callbacks from a previous Voice Lab run from entering a new run. */
object VoiceLabAudioPolicy {
    fun isCurrentRun(candidate: Long, current: Long, running: Boolean): Boolean =
        running && candidate == current

    fun isCurrentUtterance(candidate: Long, current: Long): Boolean = candidate == current

    fun normalizedRmsFromSpeechDb(rmsDb: Float): Double {
        if (!rmsDb.isFinite()) return 0.0
        return 10.0.pow((rmsDb / 20.0).toDouble()).coerceIn(0.0, 1.0)
    }
}
