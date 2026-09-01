package com.example.campusai.data.focus.scene

import com.example.campusai.data.focus.voice.FocusVoicePhase

object FocusAmbientPolicy {
    private const val VOICE_DUCK_FACTOR = 0.18f

    fun targetVolume(
        settings: FocusSceneSettings,
        sessionRunning: Boolean,
        appForeground: Boolean,
        phase: FocusVoicePhase,
    ): Float {
        if (!settings.ambientEnabled || !sessionRunning || !appForeground) return 0f
        return if (phase.shouldDuckAmbientSound()) {
            settings.volume * VOICE_DUCK_FACTOR
        } else {
            settings.volume
        }
    }

    private fun FocusVoicePhase.shouldDuckAmbientSound(): Boolean = when (this) {
        FocusVoicePhase.LISTENING,
        FocusVoicePhase.THINKING,
        FocusVoicePhase.SPEAKING,
        -> true
        FocusVoicePhase.IDLE,
        FocusVoicePhase.CONNECTING,
        FocusVoicePhase.RECONNECTING,
        FocusVoicePhase.ERROR,
        -> false
    }
}
