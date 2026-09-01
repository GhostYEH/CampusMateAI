package com.example.campusai.data.focus.scene

import com.example.campusai.data.focus.voice.FocusVoicePhase
import org.junit.Assert.assertEquals
import org.junit.Test

class FocusAmbientPolicyTest {
    private val enabledSettings = FocusSceneSettings.DEFAULT.copy(
        ambientEnabled = true,
        volume = 0.5f,
    )

    @Test
    fun soundRequiresOptInRunningSessionAndForegroundPage() {
        assertEquals(0.5f, FocusAmbientPolicy.targetVolume(enabledSettings, true, true, FocusVoicePhase.IDLE))
        assertEquals(0f, FocusAmbientPolicy.targetVolume(enabledSettings, false, true, FocusVoicePhase.IDLE))
        assertEquals(0f, FocusAmbientPolicy.targetVolume(enabledSettings, true, false, FocusVoicePhase.IDLE))
        assertEquals(
            0f,
            FocusAmbientPolicy.targetVolume(
                enabledSettings.copy(ambientEnabled = false),
                sessionRunning = true,
                appForeground = true,
                phase = FocusVoicePhase.IDLE,
            ),
        )
    }

    @Test
    fun liveVoiceDucksAmbientSound() {
        listOf(
            FocusVoicePhase.LISTENING,
            FocusVoicePhase.THINKING,
            FocusVoicePhase.SPEAKING,
        ).forEach { phase ->
            assertEquals(
                0.09f,
                FocusAmbientPolicy.targetVolume(enabledSettings, true, true, phase),
                0.0001f,
            )
        }
        assertEquals(0.5f, FocusAmbientPolicy.targetVolume(enabledSettings, true, true, FocusVoicePhase.CONNECTING))
    }
}
